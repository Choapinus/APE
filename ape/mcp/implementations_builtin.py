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
    summarize_text_impl,
)
from ape.mcp.plugin import tool
from ape.mcp.models import (
    ExecuteDatabaseQueryRequest, ExecuteDatabaseQueryResponse,
    ConversationHistoryRequest, ConversationHistoryResponse,
    SearchConversationsRequest, GenericTextResponse,
)
from ape.resources import read_resource as _read_resource

# Input schemas reused from server earlier definition

execute_query_schema = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "SQL query to execute"},
    },
    "required": ["query"],
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
async def get_database_info(**_):  # accept & ignore any extraneous args
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

# ---------------------------------------------------------------------------
# 🆕 Resource wrapper tool
# ---------------------------------------------------------------------------
resource_schema = {
    "type": "object",
    "properties": {
        "uri": {
            "type": "string",
            "description": "Registry URI to read (e.g. conversation://recent, schema://tables)"
        },
        "limit": {
            "type": "integer",
            "description": "Optional limit parameter supported by some resources",
            "default": 20
        }
    },
    "required": ["uri"],
}

@tool("read_resource", "Read a registry resource (conversation://*, schema://*, …)", resource_schema)
async def read_resource_tool(uri: str, limit: int | None = None):
    """Expose Resource Registry via a standard tool call so the LLM can read URIs autonomously."""
    ALLOWED_SCHEMES = ("conversation://", "schema://")

    if not any(uri.startswith(s) for s in ALLOWED_SCHEMES):
        return f"SECURITY_ERROR: URI scheme not permitted: {uri}"

    try:
        if limit is not None:
            mime, content = await _read_resource(uri, limit=limit)
        else:
            mime, content = await _read_resource(uri)
        # Guard: cap payload size to 64k to avoid memory abuse
        MAX_LEN = 65536
        if len(content) > MAX_LEN:
            return "SECURITY_ERROR: Resource content exceeds safe size limit"

        # MIME-type whitelist – allow only safe text-based formats
        ALLOWED_MIME = ("application/json", "text/plain", "text/markdown")
        if mime not in ALLOWED_MIME:
            return f"SECURITY_ERROR: MIME type '{mime}' not permitted"

        return content
    except Exception as exc:
        return f"ERROR reading resource {uri}: {exc}"

# ---------------------------------------------------------------------------
# 🆕 Summarise Text Tool
# ---------------------------------------------------------------------------

summarize_schema = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "Text to be summarised (max 4000 tokens)"},
    },
    "required": ["text"],
}

@tool("summarize_text", "Return a concise summary of the provided text", summarize_schema)
async def summarize_text(**kwargs):
    """Expose :pyfunc:`ape.mcp.implementations.summarize_text_impl` via MCP."""
    # Pass through validated params to the impl function
    text: str = kwargs["text"]

    summary = await summarize_text_impl(text)
    # The tool contract demands *plain text* → ensure string return
    return summary 