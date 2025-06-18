from __future__ import annotations

import json
from typing import Tuple

from loguru import logger

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.mcp.session_manager import get_session_manager


@register
class ErrorLogAdapter(ResourceAdapter):
    """Expose recent tool errors via Resource URI.

    Example::
        content, mime = await read_resource("errors://recent?limit=10")
    """

    uri_patterns = [
        "errors://recent",
    ]

    catalog = [
        ResourceMeta(
            uri="errors://recent",
            name="Recent tool errors",
            description="Returns the most recent tool errors (default limit=20)",
            type_="application/json",
        ),
    ]

    async def read(self, uri: str, **query) -> Tuple[str, str]:
        if uri == "errors://recent":
            limit = int(query.get("limit", 20))
            session_id = query.get("session_id")
            sm = get_session_manager()
            try:
                errors = await sm.a_get_recent_errors(limit, session_id=session_id)
            except Exception as exc:
                logger.error(f"[ErrorLogAdapter] Failed to fetch recent errors: {exc}")
                errors = []
            return "application/json", json.dumps(errors, indent=2, default=str)

        raise ValueError(f"ErrorLogAdapter cannot handle URI {uri}") 