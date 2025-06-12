from __future__ import annotations

from ape.mcp.implementations import (
    execute_database_query_impl,
    get_conversation_history_impl,
    get_database_info_impl,
    search_conversations_impl,
    list_available_tools_impl,
    get_last_N_user_interactions_impl,
    get_last_N_tool_interactions_impl,
    get_last_N_agent_interactions_impl,
)
from ape.mcp.plugin import tool

# Input schemas reused from server earlier definition

execute_query_schema = {
    "type": "object",
    "properties": {
        "sql_query": {"type": "string", "description": "SQL query to execute"},
        "query": {"type": "string", "description": "Alias for sql_query"},
    },
    "required": ["sql_query"],
}

@tool("execute_database_query", "Execute a SQL query on the conversation database.", execute_query_schema)
async def execute_database_query(**kwargs):
    sql_query = kwargs.get("sql_query") or kwargs.get("query", "")
    return await execute_database_query_impl(sql_query)

history_schema = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "limit": {"type": "integer", "default": 10},
    },
}

@tool("get_conversation_history", "Retrieve recent conversation history", history_schema)
async def get_conversation_history(**kwargs):
    return await get_conversation_history_impl(kwargs.get("session_id"), kwargs.get("limit", 10))

@tool("get_database_info", "Get database schema and stats", {"type": "object", "properties": {}})
async def get_database_info():
    return await get_database_info_impl()

search_schema = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer", "default": 5},
    },
    "required": ["query"],
}

@tool("search_conversations", "Search conversation history", search_schema)
async def search_conversations(**kwargs):
    return await search_conversations_impl(kwargs.get("query", ""), kwargs.get("limit", 5))

@tool("list_available_tools", "List all available tools", {"type": "object", "properties": {}})
async def list_available_tools():
    return await list_available_tools_impl()

n_inter_schema = {
    "type": "object",
    "properties": {
        "n": {"type": "integer", "default": 5},
        "session_id": {"type": "string"},
    },
}

@tool("get_last_N_user_interactions", "Last N user messages", n_inter_schema)
async def last_user_interactions(**kwargs):
    return await get_last_N_user_interactions_impl(kwargs.get("n", 5), kwargs.get("session_id"))

@tool("get_last_N_tool_interactions", "Last N tool calls", n_inter_schema)
async def last_tool_interactions(**kwargs):
    return await get_last_N_tool_interactions_impl(kwargs.get("n", 5), kwargs.get("session_id"))

@tool("get_last_N_agent_interactions", "Last N agent outputs", n_inter_schema)
async def last_agent_interactions(**kwargs):
    return await get_last_N_agent_interactions_impl(kwargs.get("n", 5), kwargs.get("session_id")) 