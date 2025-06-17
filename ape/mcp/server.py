"""Main MCP server for APE (Advanced Prompt Engine)."""

import json
import asyncio
from typing import Any, Sequence
import hmac, hashlib
from uuid import uuid4
import os

import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from loguru import logger
from ape.utils import setup_logger

from .session_manager import get_session_manager
from .plugin import discover
from ape.mcp.models import ErrorEnvelope, ToolCall, ToolResult
from ape.prompts import list_prompts as _list_prompts, render_prompt


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tools and resources."""
    
    # Initialize the MCP server using the official SDK
    server = Server("ape-server")
    registry = discover()

    SECRET = os.environ.get("MCP_HMAC_KEY", "dev-secret").encode()

    def _sign(result_id: str, payload: str) -> str:
        return hmac.new(SECRET, f"{result_id}{payload}".encode(), hashlib.sha256).hexdigest()

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools."""
        return [
            types.Tool(name=name, description=meta["description"], inputSchema=meta["inputSchema"])
            for name, meta in registry.items()
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool calls."""
        if arguments is None:
            arguments = {}
        
        logger.info(f"🔧 [MCP SERVER] Tool called: {name} with arguments: {arguments}")
        
        try:
            if name not in registry:
                error_msg = f"Tool '{name}' not found."
                logger.error(error_msg)
                envelope = ErrorEnvelope(error=error_msg, tool=name, request=ToolCall(name=name, arguments=arguments))
                get_session_manager().save_error(name, arguments, error_msg)
                return [types.TextContent(type="text", text=envelope.model_dump_json())]

            impl_fn = registry[name]["fn"]
            # ensure kwargs compatible
            result_text = await impl_fn(**arguments)

            # Wrap successful result in a ToolResult and HMAC-signed envelope
            payload_str = ToolResult(
                tool=name,
                arguments=arguments,
                result=result_text,
            ).model_dump_json()
            rid = str(uuid4())
            envelope = {
                "result_id": rid,
                "payload": payload_str,
                "sig": _sign(rid, payload_str),
            }

            return [types.TextContent(type="text", text=json.dumps(envelope))]

        except Exception as e:
            logger.error(f"💥 [MCP SERVER] Error handling tool {name}: {e}")
            err_text = str(e)
            envelope = ErrorEnvelope(error=err_text, tool=name, request=ToolCall(name=name, arguments=arguments))
            get_session_manager().save_error(name, arguments, err_text)
            return [types.TextContent(type="text", text=envelope.model_dump_json())]

    @server.list_prompts()
    async def handle_list_prompts() -> list[Any]:
        """Expose all prompts loaded from ``ape/prompts`` to the agent."""

        # Retrieve model classes from the SDK if they exist – fall back to a
        # simple ``dict`` representation otherwise so the JSON payload still
        # contains the expected fields on the wire.

        PromptModel = getattr(types, "Prompt", dict)  # type: ignore[var-annotated]
        ArgModel = (
            getattr(types, "PromptArgument", None)
            or getattr(types, "Argument", None)
            or dict
        )  # type: ignore[var-annotated]

        prompt_objs: list[Any] = []
        for p in _list_prompts():
            try:
                if PromptModel is dict:
                    prompt_objs.append(p.dict())
                else:
                    prompt_objs.append(
                        PromptModel(
                            name=p.name,
                            description=p.description,
                            arguments=[
                                (
                                    ArgModel(
                                        name=a.name,
                                        description=a.description,
                                        required=a.required,
                                    )
                                    if ArgModel is not dict
                                    else {
                                        "name": a.name,
                                        "description": a.description,
                                        "required": a.required,
                                    }
                                )
                                for a in p.arguments
                            ],
                        )
                    )
            except Exception as exc:
                logger.warning(f"⚠️  Could not convert prompt '{p.name}': {exc}")

        return prompt_objs  # type: ignore[return-value]

    @server.get_prompt()
    async def handle_get_prompt(name: str, arguments: dict | None = None) -> str:
        """Render a prompt by *name* using the internal registry."""

        try:
            rendered = render_prompt(name, arguments or {})
            return rendered
        except KeyError:
            raise ValueError(f"Prompt '{name}' not found.")

    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        """List available resources."""
        return [
            types.Resource(
                uri="conversation://sessions",
                name="All conversation sessions",
                description="Information about all conversation sessions"
            ),
            types.Resource(
                uri="conversation://recent",
                name="Recent messages",
                description="Recent messages across all sessions"
            )
        ]

    @server.read_resource()
    async def handle_read_resource(uri: str) -> str:
        """Handle resource reading."""
        logger.info(f"📖 [MCP SERVER] Resource requested: {uri}")
        
        try:
            if uri == "conversation://sessions":
                logger.info("👥 [MCP SERVER] Fetching all conversation sessions")
                session_manager = get_session_manager()
                sessions = session_manager.get_all_sessions()
                
                if not sessions:
                    result = "No conversation sessions found."
                else:
                    result = json.dumps(sessions, indent=2)
                
                logger.info(f"✅ [MCP SERVER] Sessions resource retrieved, {len(sessions)} sessions found")
                return result
                
            elif uri == "conversation://recent":
                logger.info("🕒 [MCP SERVER] Fetching recent messages across all sessions")
                result = await get_conversation_history_impl(None, 20)
                logger.info(f"✅ [MCP SERVER] Recent messages resource retrieved")
                return result
                
            else:
                logger.error(f"❌ [MCP SERVER] Unknown resource requested: {uri}")
                raise ValueError(f"Unknown resource: {uri}")
                
        except Exception as e:
            logger.error(f"💥 [MCP SERVER] Error reading resource {uri}: {e}")
            return f"Error reading resource: {str(e)}"

    return server


async def run_server():
    """Run the MCP server."""
    # ensure sinks configured
    setup_logger()

    logger.info("🚀 [MCP SERVER] Starting APE MCP Server...")
    
    server = create_mcp_server()
    logger.info("⚙️ [MCP SERVER] Server created with tools and resources configured")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("📡 [MCP SERVER] STDIO streams established, server ready for connections")
        
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ape-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        
        logger.info("🛑 [MCP SERVER] Server shutdown")


if __name__ == "__main__":
    # Run the MCP server
    asyncio.run(run_server()) 