from __future__ import annotations

from typing import Tuple
import json
from urllib.parse import urlparse, parse_qs

from ape.resources import register, ResourceAdapter, ResourceMeta
from ape.core.vector_memory import get_vector_memory
from ape.settings import settings


@register
class MemoryResourceAdapter(ResourceAdapter):
    uri_patterns = [
        "memory://semantic_search",
        "memory://add",
    ]

    catalog = [
        ResourceMeta(
            uri="memory://semantic_search",
            name="Semantic search over long-term memory",
            description="Finds the top-k most relevant text snippets from the agent's long-term memory given a query string.",
            type_="application/json",
            parameters={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The URI for the semantic search, including the query parameter 'q'. For example: memory://semantic_search?q=my-query"
                    }
                },
                "required": ["uri"]
            }
        ),
        ResourceMeta(
            uri="memory://add",
            name="Add to long-term memory",
            description="Adds a new text snippet to the agent's long-term memory.",
            type_="text/plain",
            parameters={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The URI for adding to memory. For example: memory://add"
                    },
                    "content": {
                        "type": "string",
                        "description": "The text to add to memory."
                    }
                },
                "required": ["uri", "content"]
            }
        ),
    ]

    async def read(self, uri: str, **kwargs) -> Tuple[str, str]:
        parsed_uri = urlparse(uri)
        if parsed_uri.path == "/semantic_search":
            query_params = parse_qs(parsed_uri.query)
            search_query = query_params.get("q", [None])[0]
            
            if not search_query:
                raise ValueError("Missing 'q' parameter for memory search.")

            top_k = int(kwargs.get("top_k", settings.VECTOR_SEARCH_TOP_K))

            vector_memory = await get_vector_memory()
            results = await vector_memory.search(search_query, top_k=top_k)
            
            return "application/json", json.dumps(results, indent=2, default=str)

        raise ValueError(f"MemoryResourceAdapter cannot handle URI {uri}")

    async def write(self, uri: str, content: str, **kwargs) -> None:
        parsed_uri = urlparse(uri)
        if parsed_uri.path == "/add":
            vector_memory = await get_vector_memory()
            # The add method is fire-and-forget
            vector_memory.add(content, metadata=kwargs)
            return

        raise ValueError(f"MemoryResourceAdapter cannot handle write URI {uri}")
