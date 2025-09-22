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
