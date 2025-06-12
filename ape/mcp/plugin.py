from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable, Dict, Any

_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(name: str, description: str, input_schema: dict):
    """Decorator to register an MCP tool implementation.

    Example:
        @tool("hello", "Say hello", {"type": "object", "properties": {"name": {"type": "string"}}})
        async def hello_tool(name: str = "world") -> str:
            return f"Hello {name}!"
    """

    def _decorator(fn: Callable):
        _REGISTRY[name] = {
            "fn": fn,
            "description": description,
            "inputSchema": input_schema,
        }
        return fn

    return _decorator


def discover() -> Dict[str, Dict[str, Any]]:
    """Populate registry from local modules and entry-points; return the registry."""

    # Import local implementations module to register builtin tools (side-effects)
    import importlib

    try:
        importlib.import_module("ape.mcp.implementations_builtin")
    except ModuleNotFoundError:
        # fallback to original implementations.py if not renamed
        importlib.import_module("ape.mcp.implementations")

    # Discover external entry-points
    for ep in entry_points(group="ape_mcp.tools"):
        try:
            ep.load()
        except Exception as exc:
            # Log?  simple print to avoid circular import of logger
            print(f"Failed to load tool entry-point {ep.name}: {exc}")

    return _REGISTRY