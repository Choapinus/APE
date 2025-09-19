from __future__ import annotations

from ape.resources import read_resource as _read_resource
from ape.mcp.plugin import tool

@tool(
    name="read_resource",
    description="Read a registry resource (conversation://*, schema://*, …)",
    input_schema={
        "type": "object",
        "required": ["uri"],
        "properties": {
            "uri": {"type": "string", "description": "Registry URI to read (e.g. conversation://recent, schema://tables)"},
            "query": {"type": "string", "description": "Optional query parameter supported by some resources"},
            "limit": {"type": "integer", "description": "Optional limit parameter supported by some resources"}
        }
    }
)
async def handle_read_resource(uri: str, query: str | None = None, **kwargs) -> str:
    """Delegate to resource registry adapters."""
    if query:
        uri = f"{uri}?q={query}"
    mime, content = await _read_resource(uri, **kwargs)
    # For now return plain string; mime handling TBD
    return content
