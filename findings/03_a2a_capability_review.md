# 🧩 Finding 03 – Agent-to-Agent Capability Review (A2A)
# Date: 2025-06-18

---

## 1. Background
During the June-18 design chat we examined the feasibility of enabling **Agent-to-Agent (A2A)** interactions in APE.  The objective is to let the primary agent spawn a peer agent to tackle sub-tasks, using the existing MCP tool mechanism and prompt infrastructure.

Key artefacts consulted:
* `cli_chat.py` – CLI wrapper around `ChatAgent` / `AgentCore`.
* MCP server/client abstractions (`ape.cli.mcp_client`, `ape.mcp.server`).
* Prompt/Resource registry (already exposed over MCP).
* TODO roadmap and `dev_plan.md` (post-refresh).

## 2. Current Agent State
1. **Strengths**
   * Protocol layer is solid; tools/prompts/resources round-trip cleanly.
   * Async DB + WAL + connection pool drastically reduce lock time-outs.
   * Token-budget sliding window guard prevents runaway context.
   * Centralised logging, alertable error rows (`tool_errors`).

2. **Weak Links**
   | Area | Issue | Impact |
   |------|-------|--------|
   | Error surfacing | Agent returns generic error strings despite structured `tool_errors` | Hides root-cause; tool loops repeat |
   | Summarisation | No condensation; guard simply *drops* excess tokens | Long sessions lose context |
   | Memory | Embedding index not implemented | Zero long-term recall |
   | Prompt hygiene | Mega-prompts can exceed 7-8 KiB; naive `str.format` injection risk | Context waste + security hole |
   | Loop control | Only `MAX_TOOLS_ITERATIONS`; no back-pressure for failing tools | Potential infinite loops |
   | Test coverage | No fuzz / stress tests for partial JSON streams | Hidden edge cases |

> Note Some hallucinations are model-size related (Qwen3-8B) but most are logic/data-layer issues.

## 3. A2A Tool – Concept & Design
### 3.1  Proposed MCP Tool Definition
```jsonc
{
  "name": "call_agent",
  "description": "Spawn a peer APE agent to solve a sub-task and return its answer or transcript.",
  "parameters": {
    "type": "object",
    "properties": {
      "task": {"type": "string", "description": "Prompt given to the spawned agent."},
      "context": {"type": "string", "description": "Optional additional context."},
      "max_turns": {"type": "integer", "default": 6},
      "temperature": {"type": "number", "default": 0.0}
    },
    "required": ["task"]
  }
}
```

### 3.2  Server-Side Flow
1. Receive tool call via MCP.
2. `spawn_agent()` creates a new `AgentCore` with fresh `session_id`.
3. Feed `task` (+ `context`) as the first user message.
4. Drive up to `max_turns` with streaming off (easier capture).
5. Aggregate assistant replies; return either final answer or full transcript.
6. Write ephemeral session to DB (flagged for TTL cleanup).

### 3.3  Client/LLM Integration
* Tool appears in `list_tools`; Ollama consumes it as a function tool.
* Primary agent can chain subtasks naturally: "Use `call_agent` if you need a specialised assistant".
* Depth guard: attach `x-agent-depth` counter in arguments; reject if `> 2`.

### 3.4  Guard-Rails & Constraints
| Risk | Mitigation |
|------|-----------|
| Recursive fork-bomb | Depth counter + global semaphore |
| Resource blow-up (VRAM/CPU) | Lower context & temperature for spawned agents; queue heavy jobs |
| Data leakage | Pass curated context slice, not full history |
| JWT trust chain | Sign sub-agent outputs with parent's key + sub-claim (`sub_agent_id`) |

## 4. Implementation Checklist
- [ ] Add `call_agent` tool class in **Server** (`implementations_builtin.py`).  
- [ ] Register in `ToolRegistry` with JSON schema above.  
- [ ] Extend `ClientSession` or utility wrapper for easy in-process spawn (reuse same Python process).  
- [ ] Add `depth` header & MAX_DEPTH constant.  
- [ ] CLI command `/errors` to inspect `tool_errors`.  
- [ ] Stress test: 5 nested agents, assert memory & CPU ceiling.  
- [ ] Docs: update `docs/plugins.md` and README feature list.

## 5. Roadmap Impact
1. **Error Bus CLI** ➜ must land before A2A (observability).  
2. **summarize_text** + WindowMemory ➜ high-prio (A2A multiplies text).  
3. Memory / Embeddings remains P3 but will become pain quickly once A2A spawns.

## 6. Verdict
A2A is *feasible now* with modest engineering effort (~1–2 sprint days).  It will stress-test error reporting, summarisation, and resource throttling—exactly the areas that still hurt.  Recommend implementing under a feature flag, gating depth to ≤2, and adding telemetry.