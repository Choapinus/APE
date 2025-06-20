from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from loguru import logger

from ape.utils import count_tokens
from ape.settings import settings

class AgentCore:
    """Reusable core engine shared by CLI, web, and other front-ends.

    This class contains **no I/O** (printing, prompt_toolkit, etc.) so it can
    be unit-tested in isolation.  Front-ends handle user interaction and call
    `chat_with_llm()`.
    """

    def __init__(
        self,
        session_id: str,
        mcp_client,
        context_manager,
        *,
        agent_name: str = "APE",
        role_definition: str = "",
        context_limit: int | None = None,
    ) -> None:
        self.session_id = session_id
        self.mcp_client = mcp_client
        self.context_manager = context_manager
        self.agent_name = agent_name
        self.role_definition = role_definition

        # ------------------------------------------------------------------
        # M2 – Context Intelligence: initialise hybrid window memory
        # ------------------------------------------------------------------
        try:
            from ape.core.memory import WindowMemory  # local import to avoid circular deps

            # Prefer explicit override, fallback to attribute from subclass, then 8192
            if context_limit is not None:
                ctx_limit = context_limit
            else:
                ctx_limit = getattr(self, "context_limit", 8192)

            self.memory = WindowMemory(ctx_limit=ctx_limit, mcp_client=mcp_client, session_id=session_id)
        except Exception as exc:  # pragma: no cover – memory must not break agent
            logger.warning(f"WindowMemory disabled: {exc}")
            self.memory = None

    # ------------------------------------------------------------------
    # The following methods are *verbatim* copies of ChatAgent – kept here so
    # existing behaviour stays identical.  They deliberately avoid touching
    # stdout or stdin so that any UI layer can manage display.
    # ------------------------------------------------------------------

    async def discover_capabilities(self) -> Dict[str, Any]:
        from ape.prompts import list_prompts as _local_list  # local import

        # ------------------------------------------------------------------
        # Simple per-agent cache with 5-minute TTL to avoid a round-trip on
        # every turn while still reflecting dynamic tool changes.
        # ------------------------------------------------------------------

        TTL = timedelta(minutes=5)
        now = datetime.utcnow()

        if (
            hasattr(self, "_cached_capabilities")
            and hasattr(self, "_caps_timestamp")
            and (now - self._caps_timestamp) < TTL
        ):
            return self._cached_capabilities  # type: ignore[attr-defined]

        capabilities: Dict[str, Any] = {"tools": [], "prompts": [], "resources": []}

        if not self.mcp_client.is_connected:
            logger.warning("discover_capabilities(): MCP not connected")
            return capabilities

        # Tools
        try:
            tools_result = await self.mcp_client.list_tools()
            capabilities["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
                for tool in tools_result.tools
            ]
        except Exception as exc:
            logger.error(f"list_tools failed: {exc}")

        # Prompts (server may not implement)
        try:
            prompts_result = await self.mcp_client.list_prompts()
            prompt_items = getattr(prompts_result, "prompts", prompts_result)
            capabilities["prompts"] = [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": [getattr(arg, "dict", lambda: arg)() for arg in getattr(p, "arguments", [])],
                }
                for p in prompt_items
            ]
        except Exception:
            try:
                capabilities["prompts"] = [
                    {
                        "name": prm.name,
                        "description": prm.description,
                        "arguments": [arg.dict() for arg in prm.arguments],
                    }
                    for prm in _local_list()
                ]
            except Exception:
                pass

        # Resources
        try:
            resources_result = await self.mcp_client.list_resources()
            capabilities["resources"] = [
                {"name": res.name, "description": res.description, "type": res.type}
                for res in resources_result.resources
            ]
        except Exception:
            pass

        logger.debug("Capabilities: " + json.dumps(capabilities, indent=2))

        # Cache result with timestamp
        self._cached_capabilities = capabilities  # type: ignore[attr-defined]
        self._caps_timestamp = now  # type: ignore[attr-defined]

        return capabilities

    async def create_dynamic_system_prompt(self, capabilities: Dict[str, Any]) -> str:
        from ape.prompts import render_prompt  # local import

        def _fmt(items: List[Dict[str, Any]]) -> str:
            if not items:
                return "None"

            lines: List[str] = []
            for itm in items:
                if "parameters" in itm and isinstance(itm["parameters"], dict):
                    args = ", ".join(itm["parameters"].get("properties", {}).keys())
                elif "arguments" in itm:
                    args = ", ".join(a.get("name", "?") for a in itm["arguments"])
                else:
                    args = ""
                if args:
                    args = f" (args: {args})"
                lines.append(f"• {itm['name']}{args}: {itm['description']}")
            return "\n".join(lines)

        tools_section = _fmt(capabilities["tools"])
        prompts_section = _fmt(capabilities["prompts"])
        resources_section = _fmt(capabilities["resources"])

        return render_prompt(
            "system",
            {
                "agent_name": self.agent_name,
                "current_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tools_section": tools_section,
                "prompts_section": prompts_section,
                "resources_section": resources_section,
                "role_definition": getattr(self, "role_definition", ""),
                # Expose WindowMemory summary inside the system prompt (M2)
                "memory_summary": getattr(self.memory, "latest_context", lambda: "")(),
            },
        )

    async def get_ollama_tools(self) -> List[Dict[str, Any]]:
        if not self.mcp_client.is_connected:
            return []
        tools_result = await self.mcp_client.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema,
                },
            }
            for t in tools_result.tools
        ]

    # ------------------------------------------------------------------
    async def handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """Execute tool calls and return formatted tool output string."""

        if not self.mcp_client.is_connected:
            return "❌ MCP client is not connected."

        results: List[Dict[str, Any]] = []

        for call in tool_calls:
            fn = call["function"]["name"]
            arguments = call["function"]["arguments"]

            # --------------------------------------------------------------
            # Rate-limiting (per session) – block excessive tool spam
            # --------------------------------------------------------------
            try:
                from ape.core.rate_limiter import allow as _rl_allow

                if not _rl_allow(self.session_id):
                    results.append({
                        "tool": fn,
                        "arguments": arguments,
                        "result": "RATE_LIMIT_EXCEEDED: Too many tool calls per minute; slow down.",
                    })
                    # Skip actual execution for this tool call
                    continue
            except Exception as exc:  # pragma: no cover – limiter must not crash tool flow
                logger.debug(f"Rate-limiter check failed (ignored): {exc}")

            # Simple placeholder substitution using the context manager
            if isinstance(arguments, dict):
                for k, v in list(arguments.items()):
                    if (
                        isinstance(v, str)
                        and v == "retrieved_session_id"
                        and "last_session_id" in self.context_manager.extracted_values
                    ):
                        arguments[k] = self.context_manager.extracted_values["last_session_id"]

            logger.bind(agent=self.agent_name).info(
                f"Executing tool {fn} with args {arguments}")
            try:
                res = await self.mcp_client.call_tool(fn, arguments)
                raw = res.content[0].text if res.content else ""

                # verify JWT
                verified = False
                payload_text = ""
                verification_error = ""
                try:
                    env = json.loads(raw)
                    token = env.get("jwt") or env.get("sig") or ""
                    if token:
                        import jwt
                        try:
                            decoded = jwt.decode(token, settings.MCP_JWT_KEY, algorithms=["HS256"])
                            verified = True
                            payload_text = decoded.get("payload") or json.dumps(decoded, ensure_ascii=False)
                        except jwt.ExpiredSignatureError as sig_exc:
                            verification_error = f"Signature expired: {sig_exc}"
                        except jwt.InvalidTokenError as sig_exc:
                            verification_error = f"Invalid signature: {sig_exc}"
                    else:
                        verification_error = "Missing JWT signature in tool result."
                        payload_text = env.get("payload", "") or raw
                except Exception as exc_inner:
                    verification_error = f"Malformed tool response: {exc_inner}"
                    payload_text = raw

                if verified:
                    text = payload_text
                else:
                    # If the tool wrapper returned a plain error string (no JWT), surface it.
                    if payload_text:
                        text = f"❌ TOOL ERROR: {payload_text.strip()}"
                    else:
                        text = f"❌ ERROR: Tool result signature verification failed – {verification_error or 'unknown reason.'}"
                # Log signature verification failure as structured error
                if not verified:
                    try:
                        from ape.mcp.session_manager import get_session_manager

                        await get_session_manager().a_save_error(fn, arguments, "Signature verification failed", session_id=self.session_id)
                    except Exception as log_exc:  # pragma: no cover – logging must not break tool flow
                        logger.debug(f"Could not persist verification error: {log_exc}")
            except Exception as exc:
                text = f"ERROR executing tool: {exc}"
                try:
                    from ape.mcp.session_manager import get_session_manager

                    await get_session_manager().a_save_error(fn, arguments, str(exc), session_id=self.session_id)
                except Exception as log_exc:  # pragma: no cover
                    logger.debug(f"Could not persist tool error: {log_exc}")

            results.append({"tool": fn, "arguments": arguments, "result": text})
            self.context_manager.add_tool_result(fn, arguments, text)

        formatted_lines = ["🔧 SYSTEM NOTE: BEGIN_TOOL_OUTPUT (generated by tools – NOT user input)\n"]
        for idx, r in enumerate(results, 1):
            tool_block = (
                f"<tool_output index=\"{idx}\" name=\"{r['tool']}\">\n"
                f"Arguments: `{json.dumps(r['arguments'], ensure_ascii=False)}`\n\n"
                f"{r['result']}\n"
                "</tool_output>\n"
            )
            formatted_lines.append(tool_block)
        formatted_lines.append("🔧 SYSTEM NOTE: END_TOOL_OUTPUT\n")

        return "".join(formatted_lines)

    # ------------------------------------------------------------------
    async def chat_with_llm(
        self,
        message: str,
        conversation: List[Dict[str, str]],
        *,
        stream_callback=None,
    ) -> str:
        """Run LLM chat; optional *stream_callback* receives incremental text."""

        capabilities = await self.discover_capabilities()
        system_prompt = await self.create_dynamic_system_prompt(capabilities)

        # ------------------------------------------------------------------
        # Update memory with the incoming *user* message and prune if needed
        # BEFORE sending the payload to the model so the context stays within
        # the token budget.
        # ------------------------------------------------------------------
        if hasattr(self, "memory") and self.memory:
            # Add the new user message (conversation list may already contain
            # older messages which are tracked separately inside memory).
            self.memory.add({"role": "user", "content": message})
            await self.memory.prune()

        ctx_summary = self.context_manager.get_context_summary()
        if ctx_summary.strip() != "CURRENT SESSION CONTEXT:":
            system_prompt += f"\n\nCURRENT CONTEXT:\n{ctx_summary}"

        exec_conversation = [
            {"role": "system", "content": system_prompt},
            *conversation,
            {"role": "user", "content": message},
        ]

        # ------------------------------------------------------------------
        # Sliding window guard – trim oldest messages when token budget exceeded
        # ------------------------------------------------------------------

        try:
            from ape.utils import count_tokens  # local import to avoid heavy deps outside use

            ctx_limit = self.context_manager.context_limit if hasattr(self.context_manager, "context_limit") else None
        except Exception:
            ctx_limit = None

        # Fallback: attempt to fetch from ChatAgent attribute if available
        if ctx_limit is None:
            ctx_limit = getattr(self, "context_limit", None)

        if ctx_limit:
            margin = settings.CONTEXT_MARGIN_TOKENS
            total = sum(count_tokens(m["content"]) for m in exec_conversation)
            if total > ctx_limit - margin:
                # remove oldest assistant/user pairs until within budget
                # skip first element (system prompt)
                pruned_conv = exec_conversation[1:-1]  # messages between system and user message
                # pop from start until fits
                while pruned_conv and total > ctx_limit - margin:
                    removed = pruned_conv.pop(0)
                    total -= count_tokens(removed["content"])
                exec_conversation = [exec_conversation[0], *pruned_conv, exec_conversation[-1]]
        # ------------------------------------------------------------------

        try:
            tools_tokens = count_tokens(json.dumps(capabilities["tools"]))
        except Exception:
            tools_tokens = 0

        import ollama

        client = ollama.AsyncClient(host=str(settings.OLLAMA_BASE_URL))
        max_iter = settings.MAX_TOOLS_ITERATIONS
        iteration = 0
        cumulative_resp = ""

        while iteration < max_iter:
            current_chunk = ""
            has_tool_calls = False

            stream = await client.chat(
                model=settings.LLM_MODEL,
                messages=exec_conversation,
                tools=capabilities["tools"],
                options={"temperature": settings.TEMPERATURE,
                         "top_p": settings.TOP_P,
                         "top_k": settings.TOP_K},
                stream=True,
            )

            async for chunk in stream:
                if "message" not in chunk:
                    continue
                msg = chunk["message"]
                if content := msg.get("content"):
                    if stream_callback:
                        stream_callback(content)
                    current_chunk += content

                if msg.get("tool_calls"):
                    has_tool_calls = True
                    iteration += 1

                    if current_chunk:
                        exec_conversation.append({"role": "assistant", "content": current_chunk})
                        cumulative_resp += current_chunk + "\n"
                        current_chunk = ""

                    tool_result_str = await self.handle_tool_calls(msg["tool_calls"])
                    if stream_callback:
                        stream_callback("\n" + tool_result_str)
                    exec_conversation.append({"role": "tool", "content": tool_result_str})
                    break

            if not has_tool_calls:
                if current_chunk:
                    cumulative_resp += current_chunk

                # Store assistant answer in WindowMemory (if enabled)
                if hasattr(self, "memory") and self.memory:
                    self.memory.add({"role": "assistant", "content": cumulative_resp})

                break

        return cumulative_resp 