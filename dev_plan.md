# 🛠️ Enhanced Development Plan for APE
# Generated: 2025-09-19

## 1. Key Findings
1. The MCP integration is solid, but
   - ~~Request/response payloads use ad-hoc dicts (risk of schema drift).~~ ✅ Replaced with *Pydantic* `ToolCall` / `ToolResult` / `ErrorEnvelope` models.
   - ~~Errors from tool calls are not persisted in a structured way.~~ ✅ Done via `tool_errors` table and `errors://recent` resource.
   - ~~Token counting currently requires a second Ollama call.~~ ✅ Local `TokenCounter` avoids extra Ollama request.
   - ~~Context-window trimming is manual / size-blind.~~ ✅ Sliding context-window guard implemented.
   - ~~No structured short-term (sliding) or long-term (vector) memory abstraction exists; makes scaling to multi-turn sessions brittle.~~ ✅ Implemented `AgentMemory` abstraction with `WindowMemory` and `VectorMemory`.
   - ~~No embeddings or RAG memory yet; retrieval would boost long-term reasoning.~~ ✅ FAISS-based vector memory with Ollama embeddings now provides RAG capabilities.
   - ~~Prompts & Resources are not yet exposed via MCP endpoints.~~ ✅ Exposed via `list_prompts` / `list_resources` MCP endpoints.
   - ~~Plugin discovery only covers Tools, not Prompts/Resources.~~ ✅ Unified plugin discovery now covers all three.
   - HMAC signing is present, but key handling & expiry could be improved.
   - Current persistence layer is SQLite; scalable document store options (Mongo/Postgres-JSONB) under consideration.

## 2. Strategic Initiatives

### 2.1. A Taxonomy of Agent Types

To guide our development, we will use the following taxonomy of agent types:

*   **`SolverAgent`**: The classical agent that is focused on executing tasks and answering questions. This is the agent we have implemented so far.
*   **`OrchestratorAgent`**: An agent that is specialized in managing other agents. It can delegate tasks, monitor progress, and synthesize results.
*   **`ToolSmithAgent`**: A specialized agent that can create new tools for other agents to use.
*   **`DataAnalystAgent`**: An agent that is an expert in database queries and data analysis.
*   **`SelfReflectionAgent`**: A meta-agent that is responsible for reviewing the performance of other agents and updating the system's knowledge base.

This taxonomy will help us to think more clearly about the different roles that agents can play in a multi-agent system.

### 2.2. Agent Orchestration and Sub-Task Management

Our goal is to create a heterogeneous multi-agent system where specialized "expert" agents can be created with different models, tools, and personalities. We will adopt a cautious, incremental, and experimental approach to implementing agent orchestration.

#### Phase 0: Background Task Delegation

*   **Goal**: Prove that we can successfully delegate a simple, self-contained task to a background process.
*   **Tasks**:
    1.  Implement the `subtask.py` resource adapter.
    2.  Modify the `call_slm` tool to run in the background and return a `subtask://` URI.
    3.  Implement the `get_task_status` tool.

#### Phase 1: The Minimal Viable Orchestrator

*   **Goal**: Implement a minimal `call_agent` tool that can delegate a task to a sub-agent with the same configuration as the parent.
*   **Tasks**:
    1.  Implement the minimal `call_agent` tool, using the `subtask://` resource and `get_task_status` tool from Phase 0.

#### Phase 2: Experimentation and Learning

*   **Goal**: Learn about the dynamics of our multi-agent system through experimentation.
*   **Tasks**:
    1.  Conduct a series of experiments with different agent configurations and tasks.
    2.  Document the findings in new `findings` documents.

#### Phase 3: Heterogeneous Agents

*   **Goal**: Extend the orchestration system to support heterogeneous agents with different models, tools, and personalities.
*   **Tasks**:
    1.  Extend the `call_agent` tool to allow for the configuration of the sub-agent's model, tools, and personality.
    2.  Implement the `agent_factory.py` module and the shared `MCPClient`.

#### Phase 4: Cross-Session Learning

*   **Goal**: Enable the agent to learn from its experiences and to retain knowledge across sessions.
*   **Tasks**:
    1.  Integrate the cross-session learning mechanisms we have discussed, using `VectorMemory` as a knowledge base.
    2.  Implement the "reflection" step in the `call_agent` tool.

### 2.3. Prompt System Enhancement

The current prompt system, while functional, is not as robust or extensible as the tool and resource systems. To support more advanced agentic workflows, especially for the `OrchestratorAgent`, we will enhance the prompt system with the following:

*   **Centralized Prompt Registry:** Implement a `PromptRegistry` class that discovers and manages prompt templates from the core application and external plugins using the `ape_prompts.dirs` entry point.
*   **MCP Integration:** Expose the `PromptRegistry` through the MCP server with a `list_prompts` method, allowing agents to discover available prompts at runtime.
*   **Dynamic Prompt Rendering:** Introduce a `render_prompt` tool that allows an agent to request a specific prompt by name and provide dynamic data for rendering. This will be a key enabler for the "planified orchestrator".

## 3. Immediate Objectives (📅 Sprint-0)
| Priority | Task | Owner | Notes |
|----------|------|-------|-------|
| P0 | **Done** – Fix critical startup and resource handling bugs | dev-agent | Addressed circular imports, URI parsing, and parameter handling. |
| P0 | **Done** – Introduce `TokenCounter` (local tokenizer) | dev-agent | implemented in `ape.utils.count_tokens` (uses HF `transformers`, LRU-cached) |
| P0 | **Done** – Pydantic models formalised (`ToolCall`, `ToolResult`, `ErrorEnvelope`) | dev-backend | Implemented in `ape/mcp/models.py` and integrated server ↔ agent |
| P0 | **Done** – External **Prompt Registry** & loader (`.prompt`/Jinja) | dev-platform | implemented in `ape.prompts` with hot-reload & MCP handlers |
| P0 | **Done** – Resource registry + MCP handlers (`list_resources`, `read_resource`) | dev-backend | Exposed via `conversation://` & `schema://` URIs |
| P0 | **Done** – read_resource wrapper tool (bridge Resources → Tools) | dev-backend | allows LLM to fetch any registry resource |
| P0 | **Done** – Central error bus + DB persistence | dev-backend | structured tool-error logging + `errors://recent` resource |
| P0 | **Done** – `/errors` CLI command (inspect Error Bus) | dev-backend | CLI shows per-session failures |
| P0 | **Done** – `list_available_resources` tool | dev-agent | Allows the agent to discover resources at runtime. |
| P1 | **Done** – Implement *Hybrid* summarisation policy (agent triggers `summarize_text` on overflow) | dev-agent | Implemented in `WindowMemory` |
| P1 | **Done** – Design & implement `AgentMemory` abstraction + `WindowMemory` (summarise → drop) | dev-agent | Implemented in `ape/core/memory.py` |
| P1 | **Done** – Add MCP tool `summarize_text` (server-side) | dev-backend | Implemented and used by `WindowMemory` |
| P1 | **Planned** – Implement Prompt System Enhancement | dev-platform | Create `PromptRegistry`, expose via MCP, and add `render_prompt` tool. |
| P1 | **[STALE]** – Implement a `TaskPlanner` component | dev-agent | Superseded by the Agent Orchestration plan. |
| P1 | **[STALE]** – Implement `call_agent` (A2A) tool with depth guard | dev-backend | Now part of the Agent Orchestration plan. |
| P2 | **Done** – Plugin discovery extended to Prompts & Resources | dev-platform | entry-point groups `ape_prompts.dirs`, `ape_resources.adapters` |
| P2 | **Done** – Extract public library API (clean `ape` facade) | dev-platform | re-export Agent, MCPClient; lazy CLI deps |
| P2 | **Done** – `pyproject.toml` with optional extras (`llm`, `images`, `dev`) | dev-platform | Consolidated all dependencies. |
| P2 | **Done** – Freeze dependencies via `pip-tools` | dev-platform | `requirements.txt` is now generated from `pyproject.toml`. |
| P3 | **Done** – ErrorLog resource `errors://recent` | dev-backend | model can inspect recent tool errors |
| P3 | **Done** – Rate-limiting middleware | dev-platform | prevents runaway tool loops |
| P3 | **Done** – Summarize session tool `summarize_session` | dev-agent | Existing `summarize_text` tool will be leveraged for this. |
| P3 | **Done** – Expose `memory://semantic_search` Resource | dev-ml | read-only, returns top-k snippets |
| P3 | **Done** – Memory append tool `memory_append` | dev-ml | agent can write memories to RAG store |
| P3 | **Done** – `VectorMemory` + FAISS backend | dev-ml | Implemented with FAISS backend and Ollama for embeddings. |
| P3 | **Planned** – Storage backend abstraction (`StorageBackend` interface) | dev-backend | Keep SQLite default; optional Mongo/Postgres implementation for multi-agent scaling |
| P3 | **Planned** – Reflection logger (writes to memory) | dev-agent | post-tool call success/failure notes |
| P3 | **Planned** – Self-inspect tool `self_inspect` | dev-agent | agent can query its own state & limits |
| P3 | **Planned** – Telemetry resource `health://stats` | dev-platform | uptime & latency metrics |
| P4 | **Planned** – Online prompt authoring UI | dev-frontend | web/cli playground for `.prompt` templates |
| P4 | **Planned** – Distributed agent federation PoC | dev-research | remote MCP peer discovery & trust |

## 4. Milestones
1. **Completed**
   - All chat/database ops are now awaitable; DB layer uses `aiosqlite`.
2. **M1 – Prompt & Resource Parity** *(COMPLETE)*
   - ✅ Prompt Registry implemented & served via MCP.  
   - ✅ Resource Registry implemented (`conversation://*`, `schema://*`).
   - ✅ Error Bus resource & `/errors` CLI completed.
3. **M2 – Context Intelligence** *(COMPLETE)*
   - ✅ Sliding window guard implemented.
   - ✅ Hybrid summarisation policy is complete, using `WindowMemory` and the `summarize_text` tool.
4. **M3 – Advanced Memory Architecture** *(In Progress)*
   - ✅ **Vector Memory**: Core vector memory with FAISS/Ollama is implemented.
   - **Planned – Unified Memory Manager**: Refactor `WindowMemory` and `VectorMemory` under a single, unified manager to simplify agent logic and prepare for future memory types.
   - **Planned – Pinning & Importance**: Implement the ability for the agent or user to "pin" critical messages in `WindowMemory` to prevent them from being summarized or pruned.
   - **Planned – Hybrid Context Retrieval**: Enhance the `ContextManager` to intelligently fetch and combine context from multiple sources (recency, semantic, pinned) to create a more relevant context for the LLM.
5. **M4 – Advanced Reasoning & Planning** *(PLANNED)*
   - **TaskPlanner & Procedural Memory**: Implement the `TaskPlanner` component. The generated plans and workflows will be stored in a new `ProceduralMemory` layer, allowing the agent to recall and reuse successful strategies.
   - **Reflection & Explainability**: Expand the `reflection_logger` to explicitly log all memory actions (e.g., `pin`, `append`, `search`, `prune`). The agent should be able to use this log to explain its reasoning.
   - Implement code-driven error handling and retry logic.
6. **M5 – Security Hardened**
   - JWT-style envelopes, secret rotation, CI gate for secrets.
7. **M6 – Community & UI**
   - Prompt authoring UI, plugin marketplace, rich docs.
8. **M7 – Research / Federation**
   - Distributed agents, online learning hooks.

## 6. Technical Notes
- **aiosqlite**: supports same SQL; wrap existing calls in `async with aiosqlite.connect(...)`.
- **Tokenizer**: Qwen tokeniser ≈ tiktoken `qwen.tiktoken`; fallback to `cl100k_base`.
- **Error Bus**: simple dataclass → JSON → DB; add `/errors` CLI command.
- **Embeddings**: store `(message_id, vector)`; rebuild index lazily.
- **Vector DB**: Implemented using FAISS for the index and Ollama for generating embeddings. The vector store is kept on disk under the path specified by `VECTOR_DB_PATH`.
- **Pinning**: Can be implemented by adding an `is_pinned` boolean column to the `history` table. The `WindowMemory` pruning logic must be updated to ignore pinned messages.

## 7. Testing / CI
- Unit tests for async DB, token counting edge-cases
- Integration tests: tool call → error persists
- Memory search returns deterministic top-k
- Tests for pinning: ensure pinned messages are never pruned.
- Tests for Unified Memory Manager: verify that it correctly dispatches to the underlying memory stores.

## 8. Open Questions
1. Do we need multi-tenant session isolation now or later?
2. Which embedding model balances speed ↔ memory best on WSL2?
3. Should prompts live as markdown templates or Python functions?
4. How to benchmark quality loss from overflow  → summary → drop cycle?  
5. When to chain summaries (summary-of-summaries) to avoid drift?

## 9. Next Review
Schedule design-review meeting once **M3** tasks are underway or by **2025-09-26**, whichever comes first.

## 10. Proposed Enhanced Architecture
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
    ToolRegistry --> SummarizeTool["summarize_text Tool"]
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

## 11. Expert-Level Recommendations Incorporated
- **Protocol symmetry**: Prompts & Resources now share the unified plugin registry.
- **Hybrid Memory**: vector backend abstraction planned (sqlite-vec ⇄ FAISS).
- **Writeable reflections**: `reflection_logger` & `self_inspect` tools enable meta-reasoning.
- **Security & audit**: JWT signing retained; audit trail via ErrorLog & Memory logs.
- **Community growth**: Marketplace scaffold and prompt UI scheduled for M5.
- **Research path**: Federation PoC & online learning targeted for M6.

## 12. Future Considerations
### 1. Agent Extensibility and Plugin Support
**Current:** Tool and prompt plugins are supported, but agent behaviors (reasoning strategies, action selection) are mostly hardcoded.
**Suggestion:**
- Make agent strategies pluggable, e.g., allow registering new reasoning modules, decision policies, or action planners via entry points.
- Provide a base AgentCore class with hooks (before_tool_call, after_tool_call, on_context_refresh) for easy extension.

## 13. Future Development
- **GPU Acceleration:** Optimize vector search performance by implementing a `faiss-gpu` backend. This will require a separate `Dockerfile.gpu` and a suitable NVIDIA CUDA base image.
