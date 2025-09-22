# Resources vs Tool Usage in MCP

Date: 2025-06-17  
Author: Project APE

---

## 1 . Quick recap of MCP primitives

| Primitive | Who triggers it | Purpose | Handler pair |
|-----------|-----------------|---------|--------------|
| **Tools** | *Model-controlled* (LLM) | Perform an action or retrieve data under the model's initiative | `list_tools`, `call_tool` |
| **Resources** | *Application-controlled* (host client) | Provide contextual, read-only data for the model | `list_resources`, `read_resource` |
| **Prompts** | *User-controlled* | Re-usable templates that the user can request | `list_prompts`, `get_prompt` |

(Reference: MCP README – *Server Capabilities* table.)

## 2 . Observation in APE

* Server already implements both registry handlers:
  * `@server.list_resources()` returns URIs like `conversation://sessions`, `schema://tables`.
  * `@server.read_resource()` delegates to adapter layer (ConversationAdapter, SchemaAdapter).
* However **the LLM never calls `read_resource`** because Ollama/open-function-calling only lets the model invoke *tools*.
* Therefore resources are effectively **passive**; the agent can read their catalogue but not their content.

## 3 . Why wrap resources in a tool?

1. **Channel mismatch** – The SDK distinguishes *application-controlled* vs *model-controlled* actions.  Resources belong to the former; there is no built-in "resource-call" JSON payload emitted by current LLM interfaces.
2. **Function-calling contract** – Ollama/OpenAI etc. surface *functions* (aka tools) to the model.  Anything the model should trigger must look like a function.
3. **Zero spec change** – Wrapping simply re-uses the already-stable `call_tool` path; no need to fork the MCP SDK or modify transports.
4. **Fine-grained limits** – A tool wrapper can impose pagination/size limits, redact PII, or post-process the payload before it reaches the LLM.

> In short: *the protocol exposes resources, but the model cannot initiate `read_resource` without an extra bridge*.  A thin wrapper tool fills that gap.

## 4 . Minimal wrapper design

```python
from ape.resources import read_resource as _rr
from ape.mcp.plugin import tool

schema = {
    "type": "object",
    "properties": {
        "uri":   {"type": "string", "description": "Registry URI to read"},
        "limit": {"type": "integer", "description": "Optional row/message limit"}
    },
    "required": ["uri"]
}

@tool("read_resource", "Read a registry resource (conversation://*, schema://*)", schema)
async def read_resource_tool(uri: str, limit: int | None = None):
    mime, content = await _rr(uri, limit=limit) if limit else await _rr(uri)
    return content  # mime available if branching needed
```

Once loaded the agent can invoke:
```jsonc
{
  "name": "read_resource",
  "arguments": {"uri": "schema://tables"}
}
```

## 5 . Testing checklist

- [ ] Unit: `call_tool("read_resource", {"uri": "conversation://sessions"})` returns JSON list.
- [ ] Integration: logs show `Tool called: read_resource ...` when user asks "What tables exist?".
- [ ] Prompt updated: system message instructs model to use **read_resource** for URI access.

## 6 . Future enhancements

1. **Automatic URI trigger** – Scan assistant messages for `scheme://` patterns and pre-fetch via `read_resource` in the next turn.
2. **Streaming / chunking** – For very large payloads stream first *N* KB or summarise via `summarize_text` tool.
3. **Writeable resources** – Introduce `memory_append` etc. once RAG store lands.

---

These insights guide the next incremental step: implement the wrapper tool and update tests/system-prompt so the LLM can *actively* exploit the Resource Registry. 