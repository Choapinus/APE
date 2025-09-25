# 05 – Memory Layers and Context Management

_Date: 2025-09-22_

---

## 1. Background

This document describes the current memory architecture of the APE agent and proposes a conceptual model for its future evolution. It builds upon the initial design in `01_sliding_window_memory_review.md`.

## 2. Current Memory Implementation

The APE agent currently employs a two-part memory system:

*   **`WindowMemory` (Short-Term Memory)**: This is the agent's primary working memory. It holds the most recent conversation history in a sliding window. To prevent context overflow, it automatically condenses the oldest messages into a summary using the `summarize_text` tool when the window exceeds a certain size. This acts as a form of lossy compression.

*   **`VectorMemory` (Long-Term Memory)**: This system provides the agent with long-term recall. It uses a FAISS vector store and Ollama embeddings to store and retrieve information based on semantic similarity. The `add` method operates asynchronously, embedding and storing text in the background.

## 3. A Multi-Layered Conceptual Model

While `WindowMemory` and `VectorMemory` are implemented as separate components, it is useful to think of them as part of a unified, multi-layered memory architecture:

*   **Episodic Memory**: This is the agent's record of specific events and experiences. The conversation history, managed by `WindowMemory` and persisted in the database, serves as the agent's episodic memory.

*   **Semantic Memory**: This represents the agent's general knowledge. This is primarily the knowledge embedded in the pre-trained LLM, but it is augmented by the content stored in `VectorMemory`, which can be searched for relevant information.

*   **Procedural Memory**: This is the agent's knowledge of how to perform tasks. The available tools and their descriptions constitute the agent's procedural memory.

*   **Working Memory**: This is the agent's short-term "scratchpad" for the current task. The messages currently held in `WindowMemory` represent the agent's working memory.

This layered model provides a useful framework for reasoning about the agent's cognitive abilities and for guiding the future development of its memory system.

## 4. Sub-Agent Memory Strategies

When a parent agent delegates a task to a sub-agent (as discussed in `06_agent_orchestration.md`), we must decide how to manage the sub-agent's memory. We propose the following strategy:

*   **Private Scratchpad**: The sub-agent will be created with its own private `WindowMemory` and will not inherit the parent's memory. This ensures that sub-agents are isolated and that their memory usage does not interfere with the parent.

*   **Explicit Context Passing**: The parent agent will be responsible for passing any necessary context to the sub-agent as part of the initial prompt. This makes the information flow explicit and controllable.

This approach is consistent with the principle of modularity and will allow us to build a robust and scalable multi-agent system.

## 5. Advanced Memory and Learning Strategies

Looking beyond the immediate implementation, we can consider more advanced strategies for memory and learning that will enable our agents to become more intelligent and autonomous over time.

### 5.1. What does an agent *really* need to know?

A crucial distinction must be made between **state** (the current step in a plan, the value of a variable) and **knowledge** (the fact that a certain tool is unreliable, or that a particular approach is more efficient for a given task). While our current memory system is good at storing state, we need to develop mechanisms for the agent to acquire and retrieve *meta-knowledge* about its own performance and the world.

### 5.2. Beyond Prompts and Heuristics

While prompts and hardcoded heuristics are a necessary starting point, they are not a scalable solution for encoding complex behaviors. A more advanced approach is to enable the agent to learn from its experience. This could take the form of a **"meta-agent"** or a **"self-reflection" cycle**, where the agent periodically:

1.  **Reviews its own performance**: Analyzes its successes and failures.
2.  **Identifies patterns**: Discovers that certain actions consistently lead to better outcomes.
3.  **Generates new knowledge**: Creates new "rules" or "heuristics" for itself, which can be stored in its memory.

### 5.3. Fine-Tuning and LoRA

Another powerful technique for encoding knowledge and behavior is **fine-tuning**. By training the LLM on a curated dataset of high-quality interactions, we can bake procedural knowledge and behavioral patterns directly into the model.

**Low-Rank Adaptation (LoRA)** is a particularly promising fine-tuning technique. It allows us to create small, specialized "adapter" layers that can be swapped in and out without retraining the entire model. For example, we could have:

*   A LoRA layer for **code generation**.
*   A LoRA layer for **data analysis**.
*   A LoRA layer for **creative writing**.

The agent could then dynamically load the appropriate LoRA layer based on the task at hand, effectively changing its "specialization" on the fly.

### 5.4. Generating Our Own Training Data

The conversations, tool interactions, and problem-solving traces generated by our agent are a valuable asset. This data can be used to create a high-quality dataset for fine-tuning future generations of agents. This creates a **virtuous cycle**: as the agent gets better, it generates better data, which in turn allows us to build even better agents.

### 5.5. Cross-Session Learning and Knowledge Retrieval

A key challenge in creating a truly learning agent is ensuring that knowledge is persistent and accessible across sessions. An agent that starts from zero with each new session is not truly learning. We can address this "Groundhog Day" problem with the following strategies:

*   **Structured Knowledge Storage**: We must store not just raw conversation history, but also the structured knowledge the agent generates. This includes successful plans, failed plans and their resolutions, and the agent's own reflections on its performance. Our `VectorMemory` can be used as a knowledge base for this purpose.

*   **Proactive Priming**: At the beginning of each session, we can "prime" the agent by automatically retrieving a small number of high-level heuristics or general principles from its `VectorMemory` and inserting them into the system prompt. For example: `"Remember your past successes: always verify user requirements before starting a complex task."`

*   **Reactive Retrieval**: During a task, the agent can be prompted to query its own knowledge base. For example, the system prompt could include an instruction like: `"Before using a tool, consider searching your memory for any known best practices or issues related to that tool."` The agent would then issue a `memory_search` call with a query like `"best practices for call_slm"`.

*   **Learning from Errors**: By explicitly storing both successful and failed plans in its memory, the agent can learn to recognize patterns that lead to errors and avoid them in the future. This also allows for "intelligent recovery". If an agent encounters an error, it can search its memory for similar past errors and their resolutions.

By combining these advanced memory and learning strategies, we can create agents that are not just capable of executing tasks, but are also capable of learning, adapting, and improving over time.

---

## 6. Current Implementation Status and Next Steps

_Updated: 2025-09-22 (Codebase Review)_

### 6.1. Infrastructure Assessment

Through comprehensive codebase analysis, we've discovered that **APE already has substantial memory infrastructure** that significantly accelerates development:

#### ✅ **Implemented Foundation**
- **`WindowMemory`** (`ape/core/memory.py`): Complete sliding window with summarization
  - Features: `add()`, `tokens()`, `summarize()`, `prune()`, `force_summarize()`
  - Auto-summarization using `summarize_text` tool when context limit exceeded
  - Configurable via `CONTEXT_MARGIN_TOKENS` (1024) and `SUMMARY_MAX_TOKENS` (256)

- **`VectorMemory`** (`ape/core/vector_memory.py`): FAISS-based long-term memory
  - Async embedding and storage with Ollama embeddings
  - Configurable models via `EMBEDDING_MODEL` ("embeddinggemma:latest")
  - Persistent FAISS index storage with metadata tracking
  - Search capabilities with distance scoring

- **SLM Integration** (`ape/mcp/implementations.py`): Complete `call_slm_impl()`
  - Async SLM calls with full parameter control (temperature, top_p, top_k, think mode)
  - Error handling, timeouts, and fallback mechanisms
  - Tool-ready implementation via MCP system

- **Memory Tools**: Production-ready MCP tools
  - `memory_append`: Adds text to long-term vector memory
  - `summarize_text`: Generates summaries (used by WindowMemory)
  - `call_slm`: SLM integration for metadata extraction tasks

### 6.2. Identified Gaps for Advanced Memory

While the foundation is solid, several advanced capabilities need implementation:

#### 🎯 **MetaMemory Layer** (Priority 1)
- **SLM-powered metadata extraction**: Using existing `call_slm` for content analysis
- **Memory familiarity**: "Knowing that we might know" awareness mechanisms
- **Quality assessment**: Memory precision/recall metrics and validation

#### 🔄 **Enhanced Retrieval** (Priority 2)
- **Multi-pass retrieval**: Broad → refined search mimicking human recall
- **Cue-based priming**: Association chains and context-aware ranking
- **Hybrid search**: Combining semantic similarity with keyword matching

#### 🧠 **Metacognitive Features** (Priority 3)
- **Self-reflection cycles**: Performance analysis and pattern recognition
- **Memory consolidation decisions**: Intelligent promotion from working to long-term
- **Cross-session learning**: Bootstrap new sessions with relevant past knowledge

### 6.3. Proposed Implementation Strategy

Building on existing infrastructure, we recommend a phased approach:

#### **Phase 1: MetaMemory Core (3-4 weeks)**
```python
class MetaMemory(AgentMemory):
    """Extends existing AgentMemory with SLM-powered metadata extraction"""

    def __init__(self, slm_client, window_memory, vector_memory):
        self.slm = slm_client  # Use existing call_slm_impl
        self.window = window_memory  # Existing WindowMemory
        self.vector = vector_memory  # Existing VectorMemory

    async def extract_metadata(self, text: str) -> MemoryMetadata:
        """Use SLM to extract keywords, importance, relationships"""

    async def assess_familiarity(self, query: str) -> FamiliarityScore:
        """Determine if we might have relevant knowledge"""

    async def consolidate_memory(self, chunk: List[Message]) -> bool:
        """Intelligent decision on memory promotion"""
```

#### **Phase 2: Advanced Retrieval (2-3 weeks)**
- Extend existing `VectorMemory.search()` with multi-pass capability
- Add cue-based priming using existing FAISS infrastructure
- Implement memory confidence scoring

#### **Phase 3: Cross-Session Learning (4-5 weeks)**
- Session bootstrap using existing vector search
- Knowledge distillation from conversation patterns
- Self-reflection integration with existing error logging

### 6.4. Technical Advantages

The existing infrastructure provides several advantages:

1. **Async Foundation**: All memory operations use async/await patterns
2. **MCP Integration**: Tool registration system ready for new memory tools
3. **Configuration System**: Pydantic settings for easy memory tuning
4. **Error Handling**: Structured error logging for memory operations
5. **JWT Security**: Tamper-proof tool responses for memory integrity

### 6.5. Success Metrics

Leveraging existing capabilities for baseline measurements:

- **Memory Retrieval Accuracy**: Build on current FAISS similarity scoring
- **Consolidation Latency**: Improve on current `WindowMemory.prune()` performance
- **Cross-Session Retention**: Utilize existing VectorMemory persistence
- **Search Response Time**: Optimize current FAISS IndexFlatL2 performance

### 6.6. Future Vision: Artificial Phenomenology

The ultimate goal remains creating an agent with genuine self-awareness and learning capability. With APE's solid foundation, we're well-positioned to achieve:

- **Memory-driven personality development** through accumulated experience
- **Emergent insights** from memory pattern recognition
- **Strategic learning** through self-reflection and metacognition
- **Wisdom accumulation** beyond mere fact storage

This represents a significant step toward **agents that don't just execute tasks but develop genuine understanding and growth through memory**.

_"Memory is the architecture of the mind, and APE provides the foundation for building cathedrals of consciousness."_
