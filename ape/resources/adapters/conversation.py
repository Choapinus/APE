from __future__ import annotations

from typing import Tuple
from datetime import datetime
import json

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.mcp.implementations import get_conversation_history_impl
from ape.mcp.session_manager import get_session_manager


@register
class ConversationAdapter(ResourceAdapter):
    uri_patterns = [
        "conversation://sessions",
        "conversation://recent",
        "conversation://*",
    ]

    catalog = [
        ResourceMeta(
            uri="conversation://sessions",
            name="All conversation sessions",
            description="List of session IDs with basic metadata",
            type_="application/json",
        ),
        ResourceMeta(
            uri="conversation://recent",
            name="Recent messages (all sessions)",
            description="Most recent messages across every session (default 20)",
            type_="application/json",
        ),
    ]

    async def read(self, uri: str, **query) -> Tuple[str, str]:
        if uri == "conversation://sessions":
            sm = get_session_manager()
            data = await sm.a_get_all_sessions()
            return "application/json", json.dumps(data, indent=2, default=str)

        elif uri.startswith("conversation://recent"):
            limit = int(query.get("limit", 20))
            text = await get_conversation_history_impl(None, limit)
            return "application/json", text

        elif uri.startswith("conversation://"):
            session_id = uri.replace("conversation://", "", 1)
            limit = int(query.get("limit", 50))
            text = await get_conversation_history_impl(session_id, limit)
            return "application/json", text

        raise ValueError(f"ConversationAdapter cannot handle URI {uri}") 