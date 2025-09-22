# 04 – Summarisation Approaches in APE

_Date: 2025-06-19_

Milestone-M2 introduces a hybrid window-memory that relies on the new `summarize_text` tool.  This document captures design options that were considered and the rationale for the current implementation.

## 1  Problem Statement
The agent must keep multi-turn conversations within the model context window.  When the raw transcript would overflow, the oldest chunk is condensed into a short TL;DR which still preserves intent + facts.

## 2  Candidate Solutions
1. **Heuristic (extractive)**  
   Pros: deterministic, fast, no external calls.  
   Cons: quality poor on long or unstructured text.
2. **Direct Ollama LLM call (current choice)**  
   Pros: quick to implement, leverages same local model stack, low latency (single request), decent quality.  
   Cons: couples tool to model availability; might be over-kill for very short snippets.
3. **Dedicated "summariser agent"**  
   Wrap a slim `AgentCore` instance that receives the text and returns a summary.  
   Pros: uniform architecture, can chain additional reasoning or tools, decouples summarisation policy from main agent.  
   Cons: ↑ latency + resource usage; more moving parts to test.
4. **Clean separate micro-service (language-agnostic)**  
   Deploy a small REST service running a distilled model (e.g. `bge-small`) just for summarisation.  
   Pros: isolates load; can be scaled independently.  
   Cons: infrastructure overhead, introduces network hop, less reuse of existing code.

## 3  Decision & Implementation Notes
We adopted **Option 2** for now:
* Implementation lives in `ape/mcp/implementations.py::summarize_text_impl`.
* Guard-rails: 4 k input token cap; summary truncated to requested `max_tokens`.
* Graceful fallback to the heuristic when Ollama is offline or times out (30 s).  This keeps unit tests deterministic and avoids CI flakes.
* Model selectable via new optional setting `SUMMARY_MODEL`; falls back to `LLM_MODEL`.

Should quality, latency, or cost become problematic we can migrate to Option 3 without changing the public tool contract.

### Postponed: Vector (Long-Term) Memory

The planned *VectorMemory* layer has been moved to Milestone M3.  Key open questions—embedding model choice, index backend (FAISS vs. Chroma vs. Postgres-PGVector), and persistence strategy—are still under evaluation.  This postponement keeps the M2 scope focused on short-term context management while avoiding premature decisions.

## 4  Future Work
* Add streaming support for very long inputs.  
* Explore a smaller, faster model (`gemma-2b-it`) dedicated to TL;DR.  
* Consider multi-stage summarisation (chunk-level → section-level → conversation-level) to avoid drift on very long sessions. 

## 5  Known Limitation – Large-Document Retrieval

At present the server-side `summarize_text` tool enforces a **4 000-token** input cap.  When a future tool (e.g. `read_resource`) returns a *huge* payload—say the full text of a PDF page—directly passing that blob into `summarize_text` will trigger the guard-rail and yield `SECURITY_ERROR`.

Implication: the agent will be unable to access the raw chunk unless the caller first **splits / down-samples** the content.  Two mitigation paths are already on the roadmap:

1. **Recursive summariser** (planned for M3) – automatically split large inputs and summarise each chunk hierarchically.  The final TL;DR can then be injected into the prompt while keeping the originals in VectorMemory for retrieval.
2. **VectorMemory + RAG** – instead of summarising, ingest the chunks into an embedding index and let the agent fetch only the relevant slices via semantic search.

Until one of these solutions lands, callers should pre-chunk large documents or set `skip_summarization=true` (option to be designed) when raw access is essential. 

## 6  Observed Runtime Behaviour (2025-06-19)

During manual CLI tests we noticed:

• Setting `SUMMARY_MAX_TOKENS` to very high values (e.g. 4096) causes each summary to re-introduce nearly as many tokens as were dropped, so the *Total tokens* counter keeps rising.  
  – Recommendation: keep the cap ≤ 256 for effective compression.

• If a summary is generated immediately after an assistant turn the pruning happens *one user turn later* (by design). This is acceptable but can be confusing when `/memory` is invoked right away.

• Tool envelopes (`{payload, sig}`) were initially stored verbatim in memory, inflating token counts.  Commit `e7…` now unwraps the envelope and stores only the `result` field, eliminating JWT noise.

These observations will guide the next optimisation pass (M2.1) – possibly triggering a second `prune()` after assistant messages and enforcing a tighter default `SUMMARY_MAX_TOKENS`. 

### Ensuring Net Token Reduction

To guarantee that each pruning cycle actually *reduces* the total token count the summary token cap should be tied to the size of the dropped chunk:

```python
token_cap = min(settings.SUMMARY_MAX_TOKENS, max(128, dropped_tokens // 2))
```

• If 1 252 tokens are removed, the summary may be ≤ 626 tokens, so `total_tokens` will decrease.  
• The `128` floor keeps very small summaries readable.  
• `SUMMARY_MAX_TOKENS` remains an absolute upper bound (e.g. 256).

This heuristic will be implemented in the upcoming M2.1 patch. 