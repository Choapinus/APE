from __future__ import annotations

import json
from typing import Tuple

import aiosqlite
from loguru import logger

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.settings import settings

DB_PATH = settings.SESSION_DB_PATH


@register
class SchemaAdapter(ResourceAdapter):
    uri_patterns = [
        "schema://tables",
        "schema://*/columns",
    ]

    catalog = [
        ResourceMeta(
            uri="schema://tables",
            name="Database tables list",
            description="Names of all tables in the SQLite schema",
            type_="application/json",
        )
    ]

    async def read(self, uri: str, **query) -> Tuple[str, str]:
        if uri == "schema://tables":
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
                    rows = await cur.fetchall()
                    tables = [r[0] for r in rows]
            return "application/json", json.dumps(tables)

        if uri.startswith("schema://") and uri.endswith("/columns"):
            table = uri[len("schema://") : -len("/columns")]
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute(f"PRAGMA table_info({table})") as cur:
                    cols = await cur.fetchall()
            col_meta = [dict(id=c[0], name=c[1], type=c[2]) for c in cols]
            return "application/json", json.dumps(col_meta, indent=2)

        raise ValueError(f"SchemaAdapter cannot handle URI {uri}") 