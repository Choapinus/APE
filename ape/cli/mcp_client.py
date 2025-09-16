from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from ape.settings import settings


class MCPClient:
    """Manage an MCP session over HTTP.

    Public coroutines mirror the official MCP client interface but always check
    `self.is_connected` first to avoid runtime errors.
    """

    def __init__(self):
        self._read_stream = None
        self._write_stream = None
        self._get_session_id_callback = None
        self.mcp_session: Optional[ClientSession] = None

    # ---------------------------------------------------------------------
    # Connection management
    # ---------------------------------------------------------------------
    async def connect(self) -> bool:
        """Open an MCP session over HTTP."""
        if self.mcp_session:
            logger.debug("MCPClient.connect(): already connected – skipping")
            return True

        try:
            logger.info(f"🔗 [MCP CLIENT] Connecting to MCP server at {settings.MCP_SERVER_URL}…")

            # Use the streamablehttp_client context manager
            # This yields (read_stream, write_stream, get_session_id_callback)
            # We need to enter this context manually and manage its exit.
            self._client_context = streamablehttp_client(url=str(settings.MCP_SERVER_URL))
            self._read_stream, self._write_stream, self._get_session_id_callback = await self._client_context.__aenter__()

            # Wrap the low-level streams in the higher-level ClientSession
            self.mcp_session = ClientSession(self._read_stream, self._write_stream)
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
        """Gracefully close the MCP session and underlying HTTP client."""
        try:
            if self.mcp_session:
                # The ClientSession doesn't have a close method, it relies on streams closing
                self.mcp_session = None
                logger.info("🤝 [MCP CLIENT] MCP session cleared")

            if self._client_context:
                # Exit the async context manager to close underlying HTTP client and streams
                await self._client_context.__aexit__(None, None, None)
                self._client_context = None
                self._read_stream = None
                self._write_stream = None
                self._get_session_id_callback = None
                logger.info("📡 [MCP CLIENT] HTTP client and streams closed")

            logger.info("✅ [MCP CLIENT] Disconnected successfully")
        except (RuntimeError, asyncio.CancelledError) as exc:
            logger.warning(f"Ignoring expected shutdown error: {exc}")
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