# Writing a custom MCP tool plugin

APE discovers tools at runtime via Python **entry-points**. Any external package can expose a tool with three steps:

```python
# mypkg/tools.py
from ape.mcp.plugin import tool

@tool(
    name="sentiment",
    description="Return the sentiment of a text",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)
async def sentiment(text: str) -> str:
    # your logic here – call an API, pytorch, etc.
    return "positive"
```

```toml
# pyproject.toml of your plugin package
[project.entry-points."ape_mcp.tools"]
sentiment = mypkg.tools  # module import triggers decorator registration
```

Install the package **in the same environment** as APE (`pip install -e .`).
When the MCP server starts it will import the entry-point, the decorator will register the tool, and `/tools` will list `sentiment` automatically. 