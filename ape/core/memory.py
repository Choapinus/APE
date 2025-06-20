"""APE Agent Memory Abstractions (Milestone-M2)

The module introduces a lightweight memory layer used by :pymod:`ape.core.agent_core` to keep
multi-turn chat history within the model context window.  The initial design is intentionally
simple—enough to pass unit & integration tests outlined in *todo_M2.md* while leaving head-room
for future vector/long-term memory extensions (planned M3).

Key concepts
------------
1. **AgentMemory** – an abstract base-class defining the high-level API.
2. **WindowMemory** – a concrete implementation using *hybrid summarising window* policy.

Usage (simplified)::

    mem = WindowMemory(ctx_limit=8192, mcp_client=client)
    mem.add({"role": "user", "content": "Hello world"})
    await mem.prune()  # auto-summaries + drop as required
    summary_text = mem.summary  # can be injected into the system prompt

The API signature is forward-compatible with advanced memories (VectorMemory, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List
from loguru import logger
import re
import json

from ape.settings import settings
from ape.utils import count_tokens

# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class AgentMemory(ABC):
    """Abstract memory interface consumed by :class:`ape.core.agent_core.AgentCore`."""

    @abstractmethod
    def add(self, message: Dict[str, str]) -> None:  # pragma: no cover – interface
        """Add a chat *message* (dict with ``role``/``content`` keys)."""

    @abstractmethod
    def tokens(self) -> int:  # pragma: no cover – interface
        """Return **total** token footprint of *raw* messages **plus** summaries."""

    @abstractmethod
    async def summarize(self, text: str) -> str:  # pragma: no cover – interface
        """Return a concise summary of *text*.  Implementations may call tools."""

    @abstractmethod
    async def prune(self) -> None:  # pragma: no cover – interface
        """Maybe summarise + drop messages so that :pyfunc:`tokens` fits the budget."""


# ---------------------------------------------------------------------------
# Hybrid window memory
# ---------------------------------------------------------------------------


class WindowMemory(AgentMemory):
    """Sliding window with *on-overflow summarisation* (hybrid memory).

    The class keeps *all* recent messages verbatim until the accumulated tokens
    exceed ``ctx_limit – CONTEXT_MARGIN_TOKENS``.  When that happens the oldest
    chunk(s) are concatenated, summarised via the *summarize_text* MCP tool, the
    resulting abstract is appended to :pyattr:`summary`, and the originals are
    dropped.
    """

    def __init__(self, ctx_limit: int, mcp_client, *, session_id: str | None = None):
        self.ctx_limit = ctx_limit
        self.mcp_client = mcp_client  # used to call server-side summarise tool
        self.session_id = session_id

        self.messages: List[Dict[str, str]] = []  # raw recent messages
        self.summary: str = ""  # cumulative summary text

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def add(self, message: Dict[str, str]) -> None:
        self.messages.append(message)

    def tokens(self) -> int:
        raw_tok = sum(count_tokens(m["content"]) for m in self.messages)
        summary_tok = count_tokens(self.summary)
        return raw_tok + summary_tok

    async def summarize(self, text: str) -> str:  # noqa: D401 – imperative docstring OK
        """Delegate to the *summarize_text* tool via MCP (async)."""

        try:
            res = await self.mcp_client.call_tool("summarize_text", {"text": text})
            raw = res.content[0].text if res.content else ""

            # Tool results are wrapped in a JSON envelope with signature; extract payload
            try:
                env = json.loads(raw)
                payload = env.get("payload", raw)
                # payload itself is JSON of ToolResult – result field holds the summary
                tr = json.loads(payload)
                return tr.get("result", payload)
            except Exception:
                return raw
        except Exception as exc:
            logger.error(f"WindowMemory: summarize_text tool failed: {exc}")
            # Fallback: truncate rather than break the whole flow
            tokens = text.split()
            return " ".join(tokens[:128]) if tokens else ""

    async def prune(self) -> None:
        """Summarise oldest messages until within token budget."""

        margin = settings.CONTEXT_MARGIN_TOKENS
        while self.tokens() > self.ctx_limit - margin and self.messages:
            # Heuristic: summarise the *oldest* 25% of current messages (≥1)
            batch_size = max(1, len(self.messages) // 4)
            chunk = self.messages[:batch_size]

            # Token count before removal (for metrics)
            dropped_token_count = sum(count_tokens(m["content"]) for m in chunk)
            del self.messages[:batch_size]

            text_chunk = "\n".join(m["content"] for m in chunk)

            # Optionally remove internal <think> blocks before summarisation
            if not settings.SUMMARIZE_THOUGHTS:
                text_chunk = re.sub(r"<think>.*?</think>", "", text_chunk, flags=re.S)

            summary_text = await self.summarize(text_chunk.strip())

            if summary_text:
                # Keep summaries separated by newlines for readability
                self.summary += ("\n" if self.summary else "") + summary_text

                new_token_count = count_tokens(summary_text)

                logger.debug(
                    f"[MEM] session={self.session_id or '-'} summarised_msgs={batch_size} "
                    f"dropped_tokens={dropped_token_count} new_tokens={new_token_count} "
                    f"total_tokens={self.tokens()}"
                )

                # Remove any leftover <think> blocks the summarize_text tool
                # may have echoed back so the summary stays clean.
                summary_text = re.sub(r"<think>.*?</think>", "", summary_text, flags=re.S)
            else:
                # If summarisation failed, put the messages back to avoid loss
                self.messages = chunk + self.messages
                break  # abort to avoid infinite loop

    # ------------------------------------------------------------------
    # Convenience representation
    # ------------------------------------------------------------------

    def latest_context(self) -> str:
        """Return human-readable summary suitable for prompt stuffing."""
        if not self.summary:
            return "(no summary yet)"
        return self.summary 