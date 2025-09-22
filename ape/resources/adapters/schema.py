from __future__ import annotations

from typing import Tuple
import json

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.db_pool import get_db
from ape.settings import settings


@register
class SchemaAdapter(ResourceAdapter):
    uri_patterns = [
        "schema://tables",
    ]

    catalog = [
        ResourceMeta(
            uri="schema://tables",
            name="Database schema tables",
            description="List all available table names in the conversation database schema.",
            type_="application/json",
        ),
    ]

    async def read(self, uri: str, **kwargs) -> Tuple[str, str]:
        if uri == "schema://tables":
            async with get_db(settings.SESSION_DB_PATH) as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                )
                tables = await cursor.fetchall()
                table_names = [table[0] for table in tables]
                return "application/json", json.dumps(table_names)
        raise ValueError(f"SchemaAdapter cannot handle URI {uri}")