from __future__ import annotations

from typing import Tuple
import json
import aiosqlite
from ape.settings import settings

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.mcp.session_manager import get_session_manager

DB_PATH = settings.SESSION_DB_PATH

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

        session_id = None
        if uri.startswith("conversation://recent"):
            limit = int(query.get("limit", 20))
        elif uri.startswith("conversation://"):
            session_id = uri.replace("conversation://", "", 1)
            # Guard against empty session_id if URI is just "conversation://"
            if not session_id:
                raise ValueError("Invalid URI: missing session_id in conversation://<session_id>")
            limit = int(query.get("limit", 50))
        else:
            raise ValueError(f"ConversationAdapter cannot handle URI {uri}")

        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.cursor()
                
                if session_id:
                    sql = "SELECT role, content, timestamp FROM history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?"
                    params = (session_id, limit)
                else: # for "recent"
                    sql = "SELECT role, content, timestamp FROM history ORDER BY timestamp DESC LIMIT ?"
                    params = (limit,)
                
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
            
            if not rows:
                return "application/json", json.dumps([])

            history = []
            for role, content, timestamp in reversed(rows):
                history.append({"role": role, "content": content, "timestamp": timestamp})
            
            return "application/json", json.dumps(history, indent=2)
            
        except Exception as e:
            return "application/json", json.dumps({"error": str(e)})