from __future__ import annotations

import json
import hmac, hashlib
from datetime import datetime
from typing import Any, Dict, List

import ollama
from loguru import logger

from ape.settings import settings
from ape.cli.context_manager import ContextManager
from ape.cli.mcp_client import MCPClient
from ape.utils import count_tokens, get_ollama_model_info


class ChatAgent:
    """High-level autonomous agent.

    The class is deliberately *stateless* beyond the provided `ContextManager`
    and therefore can be instantiated multiple times in the same process (for
    different user sessions).
    """

    def __init__(
        self,
        session_id: str,
        mcp_client: MCPClient,
        context_manager: ContextManager,
        *,
        agent_name: str = "APE",
    ) -> None:
        """Create a new ChatAgent.

        Parameters
        ----------
        session_id:
            Unique identifier for the end-user session.
        mcp_client:
            Connected MCPClient instance.
        context_manager:
            Per-session context storage.
        agent_name:
            Human-readable identifier (e.g. "APE-1", "APE-2") used inside the
            system prompt so that multiple agents in the same Python process
            keep their identities separate.
        """

        self.session_id = session_id
        self.mcp_client = mcp_client
        self.context_manager = context_manager
        self.agent_name = agent_name

        # ------------------------------------------------------------------
        # Cache Ollama model metadata once per agent instance for efficiency
        # ------------------------------------------------------------------
        try:
            self.model_info = get_ollama_model_info(settings.LLM_MODEL)
            self.context_limit: int | None = self.model_info.get("context_length")  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning(f"Could not retrieve model info: {exc}")
            self.model_info = {}
            self.context_limit = None

    # ------------------------------------------------------------------
    # MCP capability discovery helpers
    # ------------------------------------------------------------------
    async def discover_capabilities(self) -> Dict[str, Any]:
        """Retrieve tools / prompts / resources lists via MCP."""
        capabilities: Dict[str, Any] = {"tools": [], "prompts": [], "resources": []}

        if not self.mcp_client.is_connected:
            logger.warning("ChatAgent.discover_capabilities(): MCP not connected")
            return capabilities

        # Discover TOOLS – mandatory for proper operation
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
            logger.error(f"❌ [MCP CLIENT] list_tools failed: {exc}")

        # Discover PROMPTS – optional (older servers may not implement)
        try:
            prompts_result = await self.mcp_client.list_prompts()
            capabilities["prompts"] = [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": [arg.dict() for arg in prompt.arguments],
                }
                for prompt in prompts_result
            ]
        except Exception:
            # Don't treat as fatal – just continue without prompts
            logger.debug("MCP server does not support list_prompts – ignoring.")

        # Discover RESOURCES – optional as well
        try:
            resources_result = await self.mcp_client.list_resources()
            capabilities["resources"] = [
                {
                    "name": res.name,
                    "description": res.description,
                    "type": res.type,
                }
                for res in resources_result.resources
            ]
        except Exception:
            logger.debug("MCP server does not support list_resources – ignoring.")

        # Log final state for debugging
        logger.info(
            "🔍 [MCP CLIENT] Discovered capabilities (partial ok): "
            + json.dumps(capabilities, indent=2)
        )

        return capabilities

    # ------------------------------------------------------------------
    async def create_dynamic_system_prompt(self, capabilities: Dict[str, Any]) -> str:
        """Craft a system prompt that embeds the discovered capabilities."""
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _fmt(items: List[Dict[str, Any]], extra: str = "") -> str:
            if not items:
                return "No " + extra + "available".strip()
            if extra:
                extra = " " + extra
            return "\n".join(
                [f"• **{itm['name']}**{extra}: {itm['description']}" for itm in items]
            )

        tools_section = _fmt(capabilities["tools"])
        prompts_section = _fmt(capabilities["prompts"])
        resources_section = (
            "\n".join(
                [
                    f"• **{res['name']}** ({res['type']}): {res['description']}"
                    for res in capabilities["resources"]
                ]
            )
            if capabilities["resources"]
            else "No resources available"
        )

        return (
            f"You are {self.agent_name} (Agentic Protocol Executor), an intelligent autonomous AI assistant operating within the Model Context Protocol (MCP) framework.\n\n"
            "🔧 **YOUR CAPABILITIES:**\n"
            "You have access to powerful tools that allow you to:\n"
            "- Query databases and retrieve conversation data\n"
            "- Search through conversation history\n"
            "- Execute SQL queries for analysis\n"
            "- Retrieve session and user interaction data\n\n"
            "📊 **CURRENT SESSION:**\n"
            f"- Session ID: {self.session_id}\n"
            f"- Current Date/Time: {current_date}\n\n"
            "🛠️ **AVAILABLE TOOLS:**\n"
            f"{tools_section}\n\n"
            "📝 **AVAILABLE PROMPTS:**\n"
            f"{prompts_section}\n\n"
            "📚 **AVAILABLE RESOURCES:**\n"
            f"{resources_section}\n\n"
            "🎯 **AUTONOMOUS OPERATION PRINCIPLES:**\n"
            "1. You are capable of handling complex, multi-step tasks autonomously\n"
            "2. Use your <think> tags to reason through problems step by step\n"
            "3. Chain multiple tool calls together when needed to accomplish complex goals\n"
            "4. Build upon results from previous tools to complete comprehensive analysis\n"
            "5. Be thorough and complete - don't stop after one tool if more work is needed\n"
            "6. Synthesize information from multiple sources to provide complete answers\n"
            "7. Take initiative to gather all necessary information to fully address user requests\n"
            "8. NEVER assume or fabricate information – if data is required, first identify and execute the appropriate tool(s), then base your answer strictly on the returned results"
        )

    # ------------------------------------------------------------------
    async def get_ollama_tools(self) -> List[Dict[str, Any]]:
        """Return the MCP tools in the JSON schema expected by Ollama."""
        if not self.mcp_client.is_connected:
            return []

        tools_result = await self.mcp_client.list_tools()
        ollama_tools: List[Dict[str, Any]] = []
        for tool in tools_result.tools:
            ollama_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
            )
        return ollama_tools

    # ------------------------------------------------------------------
    async def handle_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """Execute tool calls requested by the LLM via MCP."""
        if not self.mcp_client.is_connected:
            return "❌ MCP client is not connected."

        results: List[Dict[str, Any]] = []

        for call in tool_calls:
            fn = call["function"]["name"]
            arguments = call["function"]["arguments"]

            # Simple placeholder substitution using the context manager
            if isinstance(arguments, dict):
                for k, v in list(arguments.items()):
                    if (
                        isinstance(v, str)
                        and v == "retrieved_session_id"
                        and "last_session_id" in self.context_manager.extracted_values
                    ):
                        arguments[k] = self.context_manager.extracted_values["last_session_id"]

            logger.info(f"🔧 Executing tool {fn} with args {arguments}")
            try:
                res = await self.mcp_client.call_tool(fn, arguments)
                raw = res.content[0].text if res.content else ""

                # Verify HMAC envelope
                verified = False
                payload_text = ""
                try:
                    env = json.loads(raw)
                    rid = env.get("result_id")
                    payload_text = env.get("payload", "")
                    sig = env.get("sig", "")
                    if rid and payload_text is not None and sig == self._sign(rid, payload_text):
                        verified = True
                except Exception:
                    pass

                if not verified:
                    text = "❌ ERROR: Tool result signature verification failed."
                else:
                    # Try to pretty-print ToolResult/ErrorEnvelope payloads for the LLM
                    try:
                        parsed = json.loads(payload_text)
                        if isinstance(parsed, dict):
                            # Remove overly verbose fields if any
                            text = json.dumps(parsed, indent=2)
                        else:
                            text = payload_text
                    except json.JSONDecodeError:
                        text = payload_text
            except Exception as exc:
                text = f"ERROR executing tool: {exc}"

            results.append({"tool": fn, "arguments": arguments, "result": text})
            self.context_manager.add_tool_result(fn, arguments, text)

        # Format output with explicit attribution to avoid LLM confusing the origin
        formatted = (
            "🔧 SYSTEM NOTE: The following content comes from *tool execution* — it was NOT typed by the user.\n\n"
        )
        for idx, r in enumerate(results, 1):
            formatted += f"**Tool {idx}: {r['tool']}**\nArguments: {r['arguments']}\nResult: {r['result']}\n\n"
        return formatted

    # ------------------------------------------------------------------
    async def chat_with_llm(self, message: str, conversation: List[Dict[str, str]]):
        """Stream interaction with the LLM, autonomously handling tool calls."""
        capabilities = await self.discover_capabilities()
        system_prompt = await self.create_dynamic_system_prompt(capabilities)

        # include context summary if any
        ctx_summary = self.context_manager.get_context_summary()
        if ctx_summary.strip() != "CURRENT SESSION CONTEXT:":
            system_prompt += f"\n\nCURRENT CONTEXT:\n{ctx_summary}"

        exec_conversation = [
            {"role": "system", "content": system_prompt},
            *conversation,
            {"role": "user", "content": message},
        ]

        # Pre-compute token cost for the *tools* specification once per call
        try:
            tools_tokens = count_tokens(json.dumps(capabilities["tools"]))
        except Exception:
            tools_tokens = 0

        client = ollama.AsyncClient(host=str(settings.OLLAMA_BASE_URL))
        max_iter = settings.MAX_TOOLS_ITERATIONS
        iteration = 0
        cumulative_resp = ""

        while iteration < max_iter:
            current_chunk = ""
            has_tool_calls = False

            # --------------------------------------------------------------
            # Re-evaluate prompt size each loop iteration (messages grow)
            # --------------------------------------------------------------
            try:
                # token stats for current messages
                msg_tokens = sum(count_tokens(m.get("content", "")) for m in exec_conversation)
                total_tokens = msg_tokens + tools_tokens

                # Summary line
                logger.debug(
                    f"[TokenUsage] messages_tokens={msg_tokens} | tools_tokens={tools_tokens} | "
                    f"total_tokens={total_tokens} / limit={self.context_limit if self.context_limit else 'unknown'}"
                )

                # Per-message detail
                for idx, m in enumerate(exec_conversation):
                    try:
                        tok = count_tokens(m.get("content", ""))
                        snippet = m.get("content", "")[:80].replace("\n", " ")
                        logger.debug(f"[TokenDetail] #{idx} {m['role']} tokens={tok} | {snippet}…")
                    except Exception:
                        continue

                # overflow warning if we know the limit
                if self.context_limit and total_tokens > self.context_limit:
                    excess = total_tokens - self.context_limit
                    logger.warning(
                        f"⚠️ Context window size exceeded by {excess} tokens "
                        f"({total_tokens}/{self.context_limit})."
                    )

            except Exception as exc:
                logger.debug(f"Token counting failed: {exc}")

            stream = await client.chat(
                model=settings.LLM_MODEL,
                messages=exec_conversation,
                tools=capabilities["tools"],
                options={"temperature": settings.TEMPERATURE},
                stream=True,
            )

            async for chunk in stream:
                if "message" not in chunk:
                    continue
                msg = chunk["message"]
                if content := msg.get("content"):
                    print(content, end="", flush=True)
                    current_chunk += content

                if msg.get("tool_calls"):
                    has_tool_calls = True
                    iteration += 1

                    # flush current assistant content
                    if current_chunk:
                        exec_conversation.append({"role": "assistant", "content": current_chunk})
                        cumulative_resp += current_chunk + "\n"
                        current_chunk = ""

                    tool_result_str = await self.handle_tool_calls(msg["tool_calls"])
                    print("\n" + tool_result_str)
                    exec_conversation.append({"role": "tool", "content": tool_result_str})
                    break  # restart outer while-loop to feed tool results back to LLM

            if not has_tool_calls:
                # end of LLM interaction for this message
                if current_chunk:
                    cumulative_resp += current_chunk
                break

        return cumulative_resp

    def _sign(self, rid: str, payload: str) -> str:
        return hmac.new(settings.MCP_HMAC_KEY.encode(), f"{rid}{payload}".encode(), hashlib.sha256).hexdigest() 