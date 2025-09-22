# 📝 Sliding Context-Window & Memory Management – Design Review

*Generated: 2025-06-16*

---

## 1. Background

APE currently

* streams full chat history (system prompt + every prior user / assistant / tool message) to the LLM on every request.
* monitors live token usage and logs warnings when the prompt approaches / exceeds the model's context length.

**Problem** – When a session becomes long the prompt will inevitably overflow.  We need an automatic mechanism to
shrink or externalise older content **without** breaking the agent's reasoning ability.

---

## 2. Guiding Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | *Framework-enforced quota* | Hard guarantees prevent surprise OOMs & latency spikes. |
| P2 | *LLM-transparent decisions* | Summaries / evictions happen outside of the LLM's control so behaviour is deterministic. |
| P3 | *Auditability* | All memory operations logged at DEBUG; envelope signed if done via MCP tools. |
| P4 | *Composable back-ends* | Same abstraction must cover short-term sliding window **and** long-term vector memory / RAG. |

---

## 3. Proposed Abstraction – `AgentMemory`

```python
class AgentMemory(ABC):
    async def add(self, *, role: str, content: str, timestamp: str) -> None: ...

    async def reserve_tokens(self, budget: int) -> None:
        """Shrink internal storage until the next prompt fits within *budget*."""

    async def fetch_for_prompt(self) -> list[dict]:
        """Return messages (oldest ➜ newest) to inject into the prompt."""
```

Concrete implementations planned:

| Class                | Strategy |
|----------------------|----------|
| `WindowMemory`       | Raw log ➜ summarise ➜ drop; ensures size ≤ *N* tokens. |
| `VectorMemory` (P3)  | Store embeddings; fetch top-k relevant chunks (RAG). |

---

## 4. Summarisation Strategy

*Tool-based* (`summarize_text`) recommended — keeps pipeline symmetric with other MCP calls.

1. The chunk to be condensed is sent to the MCP tool.
2. The signed `ToolResult` containing the summary is persisted **and** added to memory.
3. Original verbose messages can be deleted or archived.

Open questions:
* Summary target length – fixed token budget (e.g. ≤ 128) or adaptive?
* Chain-of-summary (summary of summaries) – when to re-summarise?

---

## 5. Integration Path – `ChatAgent`

```python
self.stm = WindowMemory(max_ctx = ctx_limit * 0.95,
                        summariser_tool = "summarize_text")
...
await self.stm.add(role, content, ts)
await self.stm.reserve_tokens(budget = ctx_limit * 0.95)
prompt_msgs = await self.stm.fetch_for_prompt()
exec_conversation = [system_prompt, *prompt_msgs, {"role": "user", ...}]
```

* Safety margin (e.g. 5 %) leaves headroom for tool schemas.
* Multiple memory layers can be consulted (vector / STM) before building the final prompt.

---

## 6. Roadmap / Tasks

| Sprint | Item | Owner |
|--------|------|-------|
| M1 | Implement `AgentMemory` base + `WindowMemory` | dev-agent |
| M1 | MCP tool `summarize_text` (async) | dev-backend |
| M1 | Wire `ChatAgent` to use `WindowMemory.reserve_tokens()` before each LLM call | dev-agent |
| M1 | Unit tests: overflow → summary injection → prompt ≤ budget | qa |
| M2 | `VectorMemory` + FAISS backing | dev-ml |
| M2 | Agent heuristics to decide when to query vector memory | dev-agent |

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Summary loses critical details | Keep raw records in DB for offline audit; allow agent to fetch originals via tool. |
| Latency of tool-based summarisation | Pre-emptively summarise when window reaches ~90 % instead of at hard limit. |
| Token drift in summariser prompt | Token-count summaries after generation & iterate until target met. |

---

## 8. Decision Needed

1. **Tool vs internal summariser** – current recommendation: MCP tool.
2. Fixed vs adaptive summary length.
3. Whether vector memory is P2 or P3 priority.

*Once these are agreed the implementation can start in the next sprint.*

## 9. Implementation Phasing & Milestones (Proposed)

| Phase | Calendar Target | Deliverable | Success Criteria |
|-------|-----------------|-------------|------------------|
| 9-A   | **Week 25**     | `AgentMemory` base class in `ape.memory` + unit tests | 100 % test pass; lint-clean |
| 9-B   | **Week 25**     | `summarize_text` MCP tool (server + schema) | Tool returns ≤ 128-token summary with HMAC envelope |
| 9-C   | **Week 26**     | `WindowMemory` implementation (summarise → drop) | Can hold 50-turn session under 3 k tokens automatically |
| 9-D   | **Week 26**     | Integrate memory into `ChatAgent`; add `--mem-debug` CLI flag | Manual test: prompt never exceeds 38 k tokens with verbose history |
| 9-E   | **Week 27**     | Regression & load tests on 500-turn synthetic chat | 95 th percentile latency ≤ 1.5 × baseline |

## 10. Evaluation / KPIs

1. **Token Budget Adherence** – percentage of LLM calls where `total_tokens ≤ context_limit` (target ≥ 99 %).
2. **Information Retention** – human evaluation: summary should preserve ≥ 90 % of factual Q&A pairs when compared to raw transcript.
3. **Latency Overhead** – median request+summary latency increase ≤ 400 ms.
4. **Storage Footprint** – DB size grows ≤ 10 % compared to raw log due to summary condensation.

Automated CI steps will calculate (1) & (3) on every PR using a dockerised mock LLM; (2) will be sampled each milestone.

## 11. Outstanding Technical Questions

| ID | Topic | Notes |
|----|-------|-------|
| Q1 | **Summary Tempering** | Do we normalise style (bullet vs prose) for downstream RAG? |
| Q2 | **AuthZ for Memory Tools** | Should summarisation and memory CRUD require elevated JWT scopes? |
| Q3 | **Cross-Session Memory** | Will we allow global memories (e.g., FAQ) accessible across sessions? |
| Q4 | **Compression vs Deletion** | After N summarisation cycles, do we gzip+archive or fully delete raw messages? |

These items will be revisited during Phase 9-C technical review.

## 12. Appendix – Example Tool Signature

```jsonc
{
  "name": "summarize_text",
  "description": "Condense a conversation chunk into ≤ 128 tokens while preserving factual content.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "Raw dialogue segment"},
      "max_tokens": {"type": "integer", "default": 128}
    },
    "required": ["text"]
  }
}
```

*Prepared by: core-dev / architecture group – please add inline comments or schedule a follow-up sync if further clarification is needed.* 