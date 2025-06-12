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
from ape.mcp.models import (
    ExecuteDatabaseQueryRequest, ExecuteDatabaseQueryResponse,
    ConversationHistoryRequest, ConversationHistoryResponse,
    SearchConversationsRequest, GenericTextResponse,
)

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
    req = ExecuteDatabaseQueryRequest(**kwargs)
    result_text = await execute_database_query_impl(req.normalized_query)
    return ExecuteDatabaseQueryResponse(result=result_text).model_dump_json()

history_schema = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "limit": {"type": "integer", "default": 10},
    },
}

@tool("get_conversation_history", "Retrieve recent conversation history", history_schema)
async def get_conversation_history(**kwargs):
    req = ConversationHistoryRequest(**kwargs)
    result_json = await get_conversation_history_impl(req.session_id, req.limit)
    return result_json

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
    req = SearchConversationsRequest(**kwargs)
    result_text = await search_conversations_impl(req.query, req.limit)
    return GenericTextResponse(result=result_text).model_dump_json()

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