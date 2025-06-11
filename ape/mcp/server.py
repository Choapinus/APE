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
    search_conversations_impl,
    list_available_tools_impl,
    get_last_N_user_interactions_impl,
    get_last_N_tool_interactions_impl,
    get_last_N_agent_interactions_impl
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
                description="Execute a SQL query on the conversation database. Supports SELECT, INSERT, UPDATE, DELETE, and table management operations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "SQL query to execute (supports SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, ALTER TABLE, etc.)"
                        },
                        "query": {
                            "type": "string", 
                            "description": "Alternative parameter name for SQL query (use sql_query preferred)"
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
            ),
            types.Tool(
                name="list_available_tools",
                description="Get information about all available MCP tools",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.Tool(
                name="get_last_N_user_interactions",
                description="Get the last N user messages from the current session to understand recent user requests",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "n": {
                            "type": "integer",
                            "description": "Number of recent user interactions to retrieve (default: 5)",
                            "default": 5
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to get interactions for (optional, uses current session if not provided)"
                        }
                    }
                }
            ),
            types.Tool(
                name="get_last_N_tool_interactions",
                description="Get the last N tool execution results from the current session to see what tools were recently used",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "n": {
                            "type": "integer",
                            "description": "Number of recent tool interactions to retrieve (default: 5)",
                            "default": 5
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to get interactions for (optional, uses current session if not provided)"
                        }
                    }
                }
            ),
            types.Tool(
                name="get_last_N_agent_interactions",
                description="Get the last N agent responses from the current session to see recent assistant outputs",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "n": {
                            "type": "integer",
                            "description": "Number of recent agent interactions to retrieve (default: 5)",
                            "default": 5
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to get interactions for (optional, uses current session if not provided)"
                        }
                    }
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
        
        logger.info(f"🔧 [MCP SERVER] Tool called: {name} with arguments: {arguments}")
        
        try:
            if name == "execute_database_query":
                # Handle both parameter names for compatibility
                sql_query = arguments.get("sql_query") or arguments.get("query", "")
                
                if not sql_query.strip():
                    error_msg = "❌ ERROR: No SQL query provided. Please provide a valid SQL query."
                    logger.error(f"📊 [MCP SERVER] {error_msg}")
                    return [types.TextContent(type="text", text=error_msg)]
                
                logger.info(f"📊 [MCP SERVER] Executing SQL query: {sql_query[:100]}...")
                result = await execute_database_query_impl(sql_query)
                logger.info(f"✅ [MCP SERVER] SQL query completed, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_conversation_history":
                session_id = arguments.get("session_id")
                limit = arguments.get("limit", 10)
                logger.info(f"📚 [MCP SERVER] Getting conversation history: session_id={session_id}, limit={limit}")
                result = await get_conversation_history_impl(session_id, limit)
                logger.info(f"✅ [MCP SERVER] Conversation history retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_database_info":
                logger.info(f"🗄️ [MCP SERVER] Getting database info")
                result = await get_database_info_impl()
                logger.info(f"✅ [MCP SERVER] Database info retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "search_conversations":
                query = arguments.get("query", "")
                limit = arguments.get("limit", 5)
                logger.info(f"🔍 [MCP SERVER] Searching conversations: query='{query}', limit={limit}")
                result = await search_conversations_impl(query, limit)
                logger.info(f"✅ [MCP SERVER] Search completed, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "list_available_tools":
                logger.info("🔧 [MCP SERVER] Listing available tools")
                result = await list_available_tools_impl()
                logger.info(f"✅ [MCP SERVER] Tool list retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_last_N_user_interactions":
                n = arguments.get("n", 5)
                session_id = arguments.get("session_id")
                logger.info(f"👤 [MCP SERVER] Getting last {n} user interactions for session: {session_id}")
                result = await get_last_N_user_interactions_impl(n, session_id)
                logger.info(f"✅ [MCP SERVER] User interactions retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_last_N_tool_interactions":
                n = arguments.get("n", 5)
                session_id = arguments.get("session_id")
                logger.info(f"🔧 [MCP SERVER] Getting last {n} tool interactions for session: {session_id}")
                result = await get_last_N_tool_interactions_impl(n, session_id)
                logger.info(f"✅ [MCP SERVER] Tool interactions retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            elif name == "get_last_N_agent_interactions":
                n = arguments.get("n", 5)
                session_id = arguments.get("session_id")
                logger.info(f"🤖 [MCP SERVER] Getting last {n} agent interactions for session: {session_id}")
                result = await get_last_N_agent_interactions_impl(n, session_id)
                logger.info(f"✅ [MCP SERVER] Agent interactions retrieved, result length: {len(result)} chars")
                return [types.TextContent(type="text", text=result)]
                
            else:
                logger.error(f"❌ [MCP SERVER] Unknown tool requested: {name}")
                raise ValueError(f"Unknown tool: {name}")
                
        except Exception as e:
            logger.error(f"💥 [MCP SERVER] Error executing tool {name}: {e}")
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