# 🛠️ Enhanced Development Plan for APE
# Generated: 2025-06-18

## 1. Key Findings
1. The MCP integration is solid, but
   - ~~Request/response payloads use ad-hoc dicts (risk of schema drift).~~ ✅ Replaced with *Pydantic* `ToolCall` / `ToolResult` / `ErrorEnvelope` models.
   - Errors from tool calls are not persisted in a structured way.
   - ~~Token counting currently requires a second Ollama call.~~ ✅ Local `TokenCounter` avoids extra Ollama request.
   - ~~Context-window trimming is manual / size-blind.~~ ✅ Sliding context-window guard implemented.
   - No structured short-term (sliding) or long-term (vector) memory abstraction exists; makes scaling to multi-turn sessions brittle.
   - No embeddings or RAG memory yet; retrieval would boost long-term reasoning.
   - ~~Prompts & Resources are not yet exposed via MCP endpoints.~~ ✅ Exposed via `list_prompts` / `list_resources` MCP endpoints.
   - ~~Plugin discovery only covers Tools, not Prompts/Resources.~~ ✅ Unified plugin discovery now covers all three.
   - HMAC signing is present, but key handling & expiry could be improved.
   - Current persistence layer is SQLite; scalable document store options (Mongo/Postgres-JSONB) under consideration.

## 2. Immediate Objectives (📅 Sprint-0)
| Priority | Task | Owner | Notes |
|----------|------|-------|-------|
| P0 | **Done** | dev-backend | Delivered in latest refactor |
| P0 | **Done** – Introduce `TokenCounter` (local tokenizer) | dev-agent | implemented in `ape.utils.count_tokens` (uses HF `transformers`, LRU-cached) |
| P0 | **Done** – Pydantic models formalised (`ToolCall`, `ToolResult`, `ErrorEnvelope`) | dev-backend | Implemented in `ape/mcp/models.py` and integrated server ↔ agent |
| P0 | **Done** – External **Prompt Registry** & loader (`.prompt`/Jinja) | dev-platform | implemented in `ape.prompts` with hot-reload & MCP handlers |
| P0 | **Done** – Resource registry + MCP handlers (`list_resources`, `read_resource`) | dev-backend | Exposed via `conversation://` & `schema://` URIs |
| P0 | **Done** – read_resource wrapper tool (bridge Resources → Tools) | dev-backend | allows LLM to fetch any registry resource |
| P0 | **Done** – Central error bus + DB persistence | dev-backend | structured tool-error logging + `errors://recent` resource |
| P0 | **Done** – `/errors` CLI command (inspect Error Bus) | dev-backend | CLI shows per-session failures |
| P1 | **Planned** – Implement *Hybrid* summarisation policy (agent triggers `summarize_text` on overflow) | dev-agent | requires `summarize_text` tool |
| P1 | Design & implement `AgentMemory` abstraction + `WindowMemory` (summarise → drop) | dev-agent | foundation for automated context trimming |
| P1 | Add MCP tool `summarize_text` (server-side) | dev-backend | used by `WindowMemory` for condensation |
| P1 | **Planned** – Implement `call_agent` (A2A) tool with depth guard | dev-backend | spawns peer agent for sub-tasks |
| P2 | Extend plugin discovery to Prompts **and** Resources | dev-platform | unify entry-point group |
| P2 | **Done** – Plugin discovery extended to Prompts & Resources | dev-platform | entry-point groups `ape_prompts.dirs`, `ape_resources.adapters` |
| P2 | **Done** – Extract public library API (clean `ape` facade) | dev-platform | re-export Agent, MCPClient; lazy CLI deps |
| P2 | **NEW** – `pyproject.toml` with optional extras (`llm`, `images`, `dev`) | dev-platform | consolidate dependency metadata |
| P2 | **NEW** – Freeze dependencies via `pip-tools` / `poetry lock` | dev-platform | reproducible builds |
| P3 | Embeddings & FAISS memory index | dev-ml | start with MiniLM-L6 or `bge-small` |
| P3 | Expose `memory://search?q=` Resource | dev-ml | read-only, returns top-k snippets |
| P3 | Memory append tool `memory_append` | dev-ml | agent can write memories to RAG store |
| P3 | ErrorLog resource `errors://recent` | dev-backend | model can inspect recent tool errors |
| P3 | Prompt list resource `prompts://list` | dev-backend | exposes prompt metadata/version |
| P3 | Summarize session tool `summarize_session` | dev-agent | stores TL;DR into embedding index |
| P3 | Rate-limiting middleware | dev-platform | prevents runaway tool loops |
| P3 | Embedding backend abstraction | dev-ml | hot-swap MiniLM/BGE/Ollama embeddings |
| P3 | Storage backend abstraction (`StorageBackend` interface) | dev-backend | Keep SQLite default; optional Mongo/Postgres implementation for multi-agent scaling |
| P3 | Telemetry resource `health://stats` | dev-platform | uptime & latency metrics |
| P3 | Online prompt authoring UI | dev-frontend | web/cli playground for `.prompt` templates |
| P3 | Self-inspect tool `self_inspect` | dev-agent | agent can query its own state & limits |
| P3 | Reflection logger (writes to memory) | dev-agent | post-tool call success/failure notes |
| P3 | `VectorMemory` + FAISS/Chroma backend | dev-ml | long-term semantic recall |
| P4 | Plugin marketplace scaffold | dev-platform | docs + entry-point registry for community |
| P4 | Distributed agent federation PoC | dev-research | remote MCP peer discovery & trust |
| P3 | Energy-aware adaptive inference (model-size / device selection) | dev-ml | minimise energy & cost; dynamic model routing |

## 3. Milestones
1. **Completed**
   - All chat/database ops are now awaitable; DB layer uses `aiosqlite`.
2. **M1 – Prompt & Resource Parity** *(COMPLETE)*
   - ✅ Prompt Registry implemented & served via MCP.  
   - ✅ Resource Registry implemented (`conversation://*`, `schema://*`).
   - ✅ Error Bus resource & `/errors` CLI completed.
3. **M2 – Context Intelligence**
   - ✅ Sliding window guard completed; next: hybrid summarisation.
   - `summarize_text` tool & WindowMemory.
4. **M3 – Memory-Augmented Agent (Vector)**
   - Embedding store, RAG resource, improved recall.
5. **M4 – Security Hardened**
   - JWT-style envelopes, secret rotation, CI gate for secrets.
6. **M5 – Community & UI**
   - Prompt authoring UI, plugin marketplace, rich docs.
7. **M6 – Research / Federation**
   - Distributed agents, online learning hooks.

## 4. Technical Notes
- **aiosqlite**: supports same SQL; wrap existing calls in `async with aiosqlite.connect(...)`.
- **Tokenizer**: Qwen tokeniser ≈ tiktoken `qwen.tiktoken`; fallback to `cl100k_base`.
- **Error Bus**: simple dataclass → JSON → DB; add `/errors` CLI command.
- **Embeddings**: store `(message_id, vector)`; rebuild index lazily.
- **FAISS**: keep index on disk under `./vector_store/`.

## 5. Testing / CI
- Unit tests for async DB, token counting edge-cases
- Integration tests: tool call → error persists
- Memory search returns deterministic top-k

## 6. Open Questions
1. Do we need multi-tenant session isolation now or later?
2. Which embedding model balances speed ↔ memory best on WSL2?
3. Should prompts live as markdown templates or Python functions?
4. How to benchmark quality loss from overflow  → summary → drop cycle?  
5. When to chain summaries (summary-of-summaries) to avoid drift?

## 7. Next Review
Schedule design-review meeting once **M1** tasks reach PR-ready state or by **2025-06-20**, whichever comes first.

## 8. Proposed Enhanced Architecture
```mermaid
%% Updated enhanced architecture with Memory layer on the far right
graph TD
  subgraph UI
    CLI["cli_chat.py"]
  end
  subgraph Agent
    ChatAgent
    ContextManager
    TokenCounter
    RateLimiter["Rate Limiter"]
  end
  CLI --> ChatAgent
  ChatAgent --> ContextManager
  ContextManager --> TokenCounter
  ContextManager --> RateLimiter
  ChatAgent -->|"LLM"| Ollama[("Ollama Server")]

  %% MCP cluster in the center
  subgraph MCP
    MCPClient
    MCPServer
  end
  ChatAgent -->|"tool_calls"| MCPClient
  MCPClient -->|"JSON-RPC"| MCPServer

  %% Server internals left-center
  subgraph Server
    MCPServer --> ToolRegistry
    MCPServer --> PromptRegistry
    MCPServer --> ResourceRegistry
    ToolRegistry --> BuiltinTools["Builtin Tools"]
    ToolRegistry --> ExternalPlugins["External Plugins"]
    ToolRegistry --> SummarizeTool["summarize_session Tool"]
    PromptRegistry --> PromptRepo["Prompt Files (.prompt)"]
    ResourceRegistry --> ResourceAdapters["Resource Adapters"]
    ResourceRegistry --> MemoryResource["Memory Resource (search & append)"]
    ResourceRegistry --> ErrorResource["ErrorLog Resource"]
    ResourceRegistry --> TelemetryRes["Health Stats Resource"]
    MCPServer --> SessionManager
    SessionManager -->|"async"| SQLiteDB[("aiosqlite DB")]
  end

  %% Memory layer explicit on the right side
  subgraph Memory_Right["Memory Layer"]
    EmbeddingIndex[("FAISS Index / Embeddings")]
  end

  ContextManager --> EmbeddingIndex
  MemoryResource --> EmbeddingIndex
```

## 9. Expert-Level Recommendations Incorporated
- **Protocol symmetry**: Prompts & Resources now share the unified plugin registry.
- **Hybrid Memory**: vector backend abstraction planned (FAISS ⇄ remote DB).
- **Writeable reflections**: `reflection_logger` & `self_inspect` tools enable meta-reasoning.
- **Security & audit**: JWT signing retained; audit trail via ErrorLog & Memory logs.
- **Community growth**: Marketplace scaffold and prompt UI scheduled for M5.
- **Research path**: Federation PoC & online learning targeted for M6.