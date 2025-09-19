from __future__ import annotations

from ape.core.vector_memory import get_vector_memory
from ape.mcp.plugin import tool

@tool(
    name="memory_add",
    description="Adds a new text snippet to the agent's long-term memory.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"}
        },
        "required": ["text"]
    }
)
async def handle_memory_add(text: str, **kwargs) -> str:
    """Adds a new text snippet to the agent's long-term memory."""
    vector_memory = await get_vector_memory()
    vector_memory.add(text, metadata=kwargs)
    return "Memory added."
