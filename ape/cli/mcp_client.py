from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Async wrapper that manages the lifecycle of an MCP stdio session.

    It hides all the boilerplate of spinning up the local *mcp_server.py* as a
    subprocess, opening the stdio transport and exposing convenience helpers
    that mirror the MCP RPC methods we use inside the CLI (list_tools,
    call_tool, list_prompts, list_resources ...).
    """

    def __init__(self, server_command: str = "python", server_script: str = "mcp_server.py"):
        self._server_command = server_command
        self._server_script = server_script

        self._stdio_context: Optional[asyncio.AbstractAsyncContextManager] = None
        self._session_context: Optional[asyncio.AbstractAsyncContextManager] = None
        self.mcp_session: Optional[ClientSession] = None

    # ---------------------------------------------------------------------
    # Connection management
    # ---------------------------------------------------------------------
    async def connect(self) -> bool:
        """Start the server (if needed) and open an MCP session over stdio."""
        if self.mcp_session:
            logger.debug("MCPClient.connect(): already connected – skipping")
            return True

        try:
            logger.info("🔗 [MCP CLIENT] Connecting to MCP server…")

            server_params = StdioServerParameters(
                command=self._server_command,
                args=[self._server_script],
                env=None,
            )

            # create the stdio transport context
            self._stdio_context = stdio_client(server_params)
            read, write = await self._stdio_context.__aenter__()
            logger.info("📡 [MCP CLIENT] STDIO connection established")

            # wrap the low-level transport in the higher-level ClientSession
            self._session_context = ClientSession(read, write)
            self.mcp_session = await self._session_context.__aenter__()
            logger.info("🤝 [MCP CLIENT] MCP session created")

            # do protocol handshake
            await self.mcp_session.initialize()
            logger.info("✅ [MCP CLIENT] MCP connection initialized successfully")

            return True
        except Exception as exc:
            logger.error(f"❌ [MCP CLIENT] Failed to connect to MCP server: {exc}")
            # make sure objects are cleaned up in case of partial failure
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Gracefully close the MCP session and underlying stdio transport."""
        try:
            if self._session_context is not None:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
                logger.info("🤝 [MCP CLIENT] MCP session closed")

            if self._stdio_context is not None:
                await self._stdio_context.__aexit__(None, None, None)
                self._stdio_context = None
                logger.info("📡 [MCP CLIENT] STDIO connection closed")

            self.mcp_session = None
            logger.info("✅ [MCP CLIENT] Disconnected successfully")
        except Exception as exc:
            logger.error(f"❌ [MCP CLIENT] Error when disconnecting: {exc}")

    # ------------------------------------------------------------------
    # Convenience pass-through helpers
    # ------------------------------------------------------------------
    async def list_tools(self):  # returns ListToolsResponse
        if not self.mcp_session:
            raise RuntimeError("MCPClient not connected – call connect() first")
        return await self.mcp_session.list_tools()

    async def list_prompts(self):
        if not self.mcp_session:
            raise RuntimeError("MCPClient not connected – call connect() first")
        return await self.mcp_session.list_prompts()

    async def list_resources(self):
        if not self.mcp_session:
            raise RuntimeError("MCPClient not connected – call connect() first")
        return await self.mcp_session.list_resources()

    async def call_tool(self, name: str, arguments: Dict[str, Any]):  # returns ToolCallResponse
        if not self.mcp_session:
            raise RuntimeError("MCPClient not connected – call connect() first")
        return await self.mcp_session.call_tool(name, arguments)

    # ------------------------------------------------------------------
    # Helpers / shortcuts
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self.mcp_session is not None 