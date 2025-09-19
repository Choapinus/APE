from __future__ import annotations

"""APE Resource Registry

Minimal MVP to expose read-only data as MCP **Resources**.  Usage::

    from ape.resources import list_resources, read_resource

    resources = list_resources()  # -> list[ResourceMeta]
    content, mime = await read_resource("conversation://sessions")

Each adapter subclassing ``ResourceAdapter`` registers itself via the
``@register`` decorator.  The registry resolves the *URI* prefix
pattern declared in the adapter.
"""

from typing import Dict, List, Tuple, Callable, Awaitable
import importlib
from pathlib import Path
import re
from importlib.metadata import entry_points  # NEW
from urllib.parse import urlparse, parse_qs
from loguru import logger

REGISTRY: Dict[str, "ResourceAdapter"] = {}


class ResourceMeta:
    def __init__(self, uri: str, name: str, description: str, type_: str = "text", parameters: dict | None = None) -> None:
        self.uri = uri
        self.name = name
        self.description = description
        self.type = type_
        self.parameters = parameters or {}

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "parameters": self.parameters,
        }


class ResourceAdapter:
    """Base class for resource adapters."""

    uri_patterns: List[str] = []  # e.g. ["conversation://*"]

    # Optional catalog for list_resources()
    catalog: List[ResourceMeta] = []

    async def read(self, uri: str, **query) -> Tuple[str, str]:
        """Return (mime_type, content).  Must be implemented by subclass."""
        raise NotImplementedError

    async def write(self, uri: str, content: str, **kwargs) -> None:
        """Write content to a resource. Must be implemented by subclass."""
        raise NotImplementedError


def register(cls: "type[ResourceAdapter]") -> "type[ResourceAdapter]":
    instance = cls()
    for pattern in cls.uri_patterns:
        REGISTRY[pattern] = instance
    return cls


# ---------------------------------------------------------------------------
# Loader (import adapters package)
# ---------------------------------------------------------------------------

def _discover_adapters() -> None:  # noqa: D401 – internal helper
    adapters_pkg = Path(__file__).with_suffix("").parent / "adapters"
    if not adapters_pkg.exists():
        return
    for py in adapters_pkg.glob("*.py"):
        if py.name == "__init__.py":
            continue
        module_name = f"ape.resources.adapters.{py.stem}"
        importlib.import_module(module_name)


_discover_adapters()

# ---------------------------------------------------------------------------
# 🔌 Plugin adapters via entry-points
# ---------------------------------------------------------------------------


def _discover_entrypoint_adapters() -> None:  # noqa: D401 – internal helper
    for ep in entry_points(group="ape_resources.adapters"):
        try:
            ep.load()  # Import triggers @register side-effects
        except Exception as exc:  # pragma: no cover
            print(f"⚠️  [ResourceRegistry] Failed to load adapter plugin '{ep.name}': {exc}")


_discover_entrypoint_adapters()

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _match_adapter(uri: str) -> ResourceAdapter | None:
    for pattern, adapter in REGISTRY.items():
        # Convert wildcard pattern to regex
        regex = re.escape(pattern).replace(r"\*", ".*")
        if re.match(regex, uri):
            return adapter
    return None


def list_resources() -> List[ResourceMeta]:
    resources: List[ResourceMeta] = []
    for adapter in set(REGISTRY.values()):
        resources.extend(adapter.catalog)
    return resources


async def read_resource(uri: str, **query) -> Tuple[str, str]:
    logger.info(f"📖 [ResourceRegistry] Reading resource: {uri} with query: {query}")
    adapter = _match_adapter(uri)
    if not adapter:
        raise ValueError(f"No adapter found for URI pattern that matches '{uri}'")
    
    query_params = parse_qs(urlparse(uri).query)
    kwargs = {k: v[0] for k, v in query_params.items()}
    kwargs.update(query)

    return await adapter.read(uri, **kwargs)

async def write_resource(uri: str, content: str, **kwargs) -> None:
    adapter = _match_adapter(uri)
    if not adapter:
        raise ValueError(f"No adapter found for URI pattern that matches '{uri}'")
    await adapter.write(uri, content, **kwargs)

__all__ = ["list_resources", "read_resource", "write_resource", "ResourceAdapter", "ResourceMeta", "register"]