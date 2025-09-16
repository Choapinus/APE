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
    """Abstract memory interface consumed by :class:`ape.core.agent_core.AgentCore`. """

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

    @abstractmethod
    async def force_summarize(self) -> None:  # pragma: no cover – interface
        """Force the entire current message buffer to be summarized and cleared."""


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
        """Summarise oldest messages, save to DB, and remove from memory."""
        from ape.mcp.session_manager import get_session_manager # Local import

        margin = settings.CONTEXT_MARGIN_TOKENS
        while self.tokens() > self.ctx_limit - margin and self.messages:
            # Heuristic: summarise the *oldest* 25% of current messages (≥1)
            batch_size = max(1, len(self.messages) // 4)
            chunk = self.messages[:batch_size]

            text_chunk = "\n".join(m["content"] for m in chunk)

            if not settings.SUMMARIZE_THOUGHTS:
                text_chunk = re.sub(r"<think>.*?</think>", "", text_chunk, flags=re.S)

            summary_text = await self.summarize(text_chunk.strip())

            if summary_text:
                try:
                    # Persist the summarization event to the database first
                    sm = get_session_manager()
                    if self.session_id:
                        await sm.a_save_summary(self.session_id, chunk, summary_text)

                    # Now, safely remove the original messages from memory
                    del self.messages[:batch_size]

                    # And append the new summary to the cumulative in-memory summary
                    self.summary += ("\n" if self.summary else "") + summary_text

                    logger.debug(
                        f"[MEM] session={self.session_id or '-'} summarised_msgs={batch_size} "
                        f"total_tokens={self.tokens()}"
                    )

                except Exception as exc:
                    logger.error(f"Failed to save summary or prune messages: {exc}")
                    # If DB save fails, do not prune messages to prevent data loss.
                    break # Abort to avoid potential infinite loop
            else:
                # If summarisation failed, do not alter memory.
                logger.warning("Summarization returned empty text, aborting prune cycle.")
                break  # abort to avoid infinite loop

    async def force_summarize(self) -> None:
        """Force the entire current message buffer to be summarized and cleared."""
        from ape.mcp.session_manager import get_session_manager  # Local import

        if not self.messages:
            logger.debug("force_summarize called with no messages to summarize.")
            return

        logger.info(f"Force summarizing {len(self.messages)} messages in buffer.")
        chunk = self.messages[:]
        text_chunk = "\n".join(m["content"] for m in chunk)

        if not settings.SUMMARIZE_THOUGHTS:
            text_chunk = re.sub(r"<think>.*?</think>", "", text_chunk, flags=re.S)

        summary_text = await self.summarize(text_chunk.strip())

        if summary_text:
            try:
                sm = get_session_manager()
                if self.session_id:
                    await sm.a_save_summary(self.session_id, chunk, summary_text)

                # Clear the entire message buffer
                self.messages.clear()

                # Append the new summary
                self.summary += ("\n" if self.summary else "") + summary_text
                logger.info("Successfully force-summarized and cleared message buffer.")

            except Exception as exc:
                logger.error(f"Failed to save summary during force_summarize: {exc}")
                # Do not clear messages if saving failed to prevent data loss.
        else:
            logger.warning("force_summarize returned empty text; buffer not cleared.")

    # ------------------------------------------------------------------
    # Convenience representation
    # ------------------------------------------------------------------

    def latest_context(self) -> str:
        """Return human-readable summary suitable for prompt stuffing."""
        if not self.summary:
            return "(no summary yet)"
        return self.summary 