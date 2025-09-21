from __future__ import annotations

from ape.tools import register
from ape.core.vector_memory import get_vector_memory

@register(
    name="memory_add",
    description="Adds a new text snippet to the agent's long-term memory.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The text to add to memory."
            }
        },
        "required": ["content"]
    }
)
async def memory_add(content: str) -> str:
    """Adds a new text snippet to the agent's long-term memory."""
    vector_memory = await get_vector_memory()
    vector_memory.add(content)
    return "Memory added successfully."
