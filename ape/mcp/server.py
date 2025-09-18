"""Main MCP server for APE (Advanced Prompt Engine)."""

import json
import asyncio
import time
from typing import Any, Sequence
from uuid import uuid4
import os

import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from loguru import logger
from ape.utils import setup_logger

from .plugin import discover
from .session_manager import get_session_manager
from ape.mcp.models import ErrorEnvelope, ToolCall, ToolResult
from ape.prompts import list_prompts as _list_prompts, render_prompt
from ape.resources import list_resources as _list_resources, read_resource as _read_resource

from ape.settings import settings  # local import to avoid circular deps

import jwt  # PyJWT
from ape.errors import ApeError  # local import


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tools and resources."""
    
    # Initialize the MCP server using the official SDK
    server = Server("ape-server")
    registry = discover()

    SECRET = settings.MCP_JWT_KEY  # str

    def _encode_token(data: dict) -> str:
        """Return HS256-signed JWT containing *data* plus issued-at timestamp."""
        now = int(time.time())
        payload = {
            **data,
            "iat": now,
            "exp": now + 600,  # token valid for 10 minutes
        }
        return jwt.encode(payload, SECRET, algorithm="HS256")

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
                await get_session_manager().a_save_error(name, arguments, error_msg, session_id=arguments.get("session_id"))
                return [types.TextContent(type="text", text=envelope.model_dump_json())]

            # ------------------------------------------------------------------
            # Sanitize arguments: drop keys not declared in the JSON schema to
            # avoid runtime errors in tool implementations that expect a fixed
            # signature (e.g. get_database_info takes no params).
            # ------------------------------------------------------------------

            schema_props = registry[name]["inputSchema"].get("properties", {})
            if schema_props:
                arguments = {k: v for k, v in arguments.items() if k in schema_props}
            else:
                # No properties defined → tool expects zero arguments
                arguments = {}

            impl_fn = registry[name]["fn"]
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
                "sig": _encode_token({"result_id": rid, "payload": payload_str}),
            }

            return [types.TextContent(type="text", text=json.dumps(envelope))]

        except Exception as e:
            logger.error(f"💥 [MCP SERVER] Error handling tool {name}: {e}")

            if isinstance(e, ApeError):
                err_payload = e.to_dict()
            else:
                err_payload = {"status": "error", "code": "UNHANDLED_EXCEPTION", "message": str(e)}

            envelope = ErrorEnvelope(error=json.dumps(err_payload), tool=name, request=ToolCall(name=name, arguments=arguments))
            await get_session_manager().a_save_error(name, arguments, err_payload.get("message", str(e)), session_id=arguments.get("session_id"))
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
        """List resources from the registry."""

        res_objs = []
        for meta in _list_resources():
            res_objs.append(
                types.Resource(
                    uri=meta.uri,
                    name=meta.name,
                    description=meta.description,
                    type=meta.type,
                )
            )
        return res_objs

    @server.read_resource()
    async def handle_read_resource(uri: str) -> str:
        """Delegate to resource registry adapters."""
        logger.info(f"📖 [MCP SERVER] Resource requested: {uri}")
        try:
            mime, content = await _read_resource(uri)
            # For now return plain string; mime handling TBD
            return content
        except Exception as e:
            logger.error(f"💥 [MCP SERVER] Error reading resource {uri}: {e}")
            raise

    return server


def run_server():
    """Run the MCP server via HTTP/SSE."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import Response
    from starlette.requests import Request
    from mcp.server.sse import SseServerTransport

    setup_logger()
    logger.info("🚀 [MCP SERVER] Starting APE MCP Server via HTTP/SSE...")

    # 1. Get the existing, fully configured MCP Server instance
    server = create_mcp_server()

    # 2. Create an SSE transport, telling it where to expect POST messages
    sse_transport = SseServerTransport("/mcp/messages")

    # 3. Define the main ASGI handler that connects the transport to the server
    async def handle_sse_connection(scope, receive, send):
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
        # Required by Starlette to have a response
        return Response(status_code=204)

    async def sse_endpoint(request: Request):
        return await handle_sse_connection(request.scope, request.receive, request._send)

    # 4. Create a Starlette app to host the SSE endpoints
    #    GET /mcp/sse - The client connects here to start the event stream.
    #    POST /mcp/messages/{session_id} - The client sends messages here.
    app = Starlette(routes=[
        Route("/mcp/sse", endpoint=sse_endpoint, methods=["GET"]),
        Mount("/mcp/messages", app=sse_transport.handle_post_message),
    ])

    # 5. Run the app with uvicorn
    logger.info(f"📡 [MCP SERVER] Starting HTTP server on port {settings.PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)


if __name__ == "__main__":
    # Run the MCP server
    run_server() 