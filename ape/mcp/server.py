"""Main MCP server for APE (Advanced Prompt Engine)."""

import json
import asyncio
from typing import Any, Sequence

import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

from loguru import logger

from .session_manager import get_session_manager
from .implementations import (
    execute_database_query_impl,
    get_conversation_history_impl,
    get_database_info_impl, 
    search_conversations_impl
)


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tools and resources."""
    
    # Initialize the MCP server using the official SDK
    server = Server("ape-server")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools."""
        return [
            types.Tool(
                name="execute_database_query",
                description="Execute a custom SQL query on the conversation database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "SQL SELECT query to execute (only SELECT statements allowed)"
                        }
                    },
                    "required": ["sql_query"]
                }
            ),
            types.Tool(
                name="get_conversation_history",
                description="Retrieve recent conversation history from the database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to get history for (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent messages to retrieve (default: 10)",
                            "default": 10
                        }
                    }
                }
            ),
            types.Tool(
                name="get_database_info",
                description="Get information about the conversation database schema and statistics",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.Tool(
                name="search_conversations",
                description="Search through conversation history using text matching",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for in conversation content"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            )
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool calls."""
        if arguments is None:
            arguments = {}
            
        try:
            if name == "execute_database_query":
                sql_query = arguments.get("sql_query", "")
                result = await execute_database_query_impl(sql_query)
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_conversation_history":
                session_id = arguments.get("session_id")
                limit = arguments.get("limit", 10)
                result = await get_conversation_history_impl(session_id, limit)
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_database_info":
                result = await get_database_info_impl()
                return [types.TextContent(type="text", text=result)]
                
            elif name == "search_conversations":
                query = arguments.get("query", "")
                limit = arguments.get("limit", 5)
                result = await search_conversations_impl(query, limit)
                return [types.TextContent(type="text", text=result)]
                
            else:
                raise ValueError(f"Unknown tool: {name}")
                
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return [types.TextContent(type="text", text=f"Error executing tool: {str(e)}")]

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
        try:
            if uri == "conversation://sessions":
                session_manager = get_session_manager()
                sessions = session_manager.get_all_sessions()
                
                if not sessions:
                    return "No conversation sessions found."
                
                return json.dumps(sessions, indent=2)
                
            elif uri == "conversation://recent":
                return await get_conversation_history_impl(None, 20)
                
            else:
                raise ValueError(f"Unknown resource: {uri}")
                
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return f"Error reading resource: {str(e)}"

    return server


async def run_server():
    """Run the MCP server."""
    server = create_mcp_server()
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
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


if __name__ == "__main__":
    # Run the MCP server
    asyncio.run(run_server()) 