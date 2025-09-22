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
    ]

    catalog = [
        ResourceMeta(
            uri="memory://semantic_search",
            name="Long-term memory search",
            description="Search the agent's long-term memory for text snippets semantically related to a query. Use 'query' parameter for the query.",
            type_="application/json",
            parameters={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The URI for the semantic search: `memory://semantic_search`"
                    },
                    "query": {
                        "type": "string",
                        "description": "The search query to be vectorized and matched against stored content."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "The number of top results to return."
                    }
                },
                "required": ["uri", "query"]
            }
        ),
    ]

    async def read(self, uri: str, **kwargs) -> Tuple[str, str]:
        parsed_uri = urlparse(uri)
        if parsed_uri.netloc == "semantic_search":
            search_query = kwargs.get("q") or kwargs.get("query")
            
            if not search_query:
                raise ValueError("Missing 'query' parameter for memory search.")

            top_k = int(kwargs.get("top_k", settings.VECTOR_SEARCH_TOP_K))

            vector_memory = await get_vector_memory()
            results = await vector_memory.search(search_query, top_k=top_k)
            
            return "application/json", json.dumps(results, indent=2, default=str)

        raise ValueError(f"MemoryResourceAdapter cannot handle URI {uri}")
