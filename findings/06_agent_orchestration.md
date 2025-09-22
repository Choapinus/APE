# 06 – Agent Orchestration and Sub-Task Management

_Date: 2025-09-22_

---

## 1. The Orchestration-Configuration-Memory Triad

Our discussions have revealed that agent orchestration is not an isolated problem. It is deeply intertwined with two other critical aspects of the agent's architecture:

*   **Configuration**: The "who" and "what" of each agent. This includes its personality (system prompt), its "size" (the LLM model it uses), and its skills (the tools and resources it has access to).
*   **Memory**: The "knowledge" of the system. This includes the agent's short-term working memory, its long-term episodic and semantic memory, and the mechanisms for sharing and retaining knowledge across sessions.

A change in one of these pillars has profound implications for the others. Therefore, a robust orchestration system must be designed with this triad in mind.

## 2. The Long-Term Vision

Our ultimate goal is to create a heterogeneous multi-agent system where:

*   Specialized "expert" agents can be created with different models, tools, and personalities.
*   The system can dynamically allocate resources, using smaller, faster models for simpler tasks.
*   The system can learn from its experiences, both within and across sessions, to improve its performance over time.

This is an ambitious but realistic goal that will guide our incremental development.

## 3. An Incremental and Experimental Approach

Given the complexity of the problem space, we will adopt a cautious, incremental, and experimental approach to implementing agent orchestration.

### 3.1. Minimal Viable Orchestrator

Our initial implementation will be a "Minimal Viable Orchestrator" (MVO). The `call_agent` tool will be as simple as possible, spawning a sub-agent that inherits the same configuration (model, tools, system prompt) as the parent.

### 3.2. The `subtask://` Resource

The cornerstone of the MVO will be the `subtask://` resource. This resource will track the state and result of the sub-task and will serve as the primary mechanism for inter-agent communication.

### 3.3. Experimentation and Learning

Once the MVO is in place, we will conduct a series of experiments to learn about the dynamics of our multi-agent system. We will manually create different "expert" agents and observe how they interact. The findings from these experiments will be documented and will guide the future development of the orchestration system.

## 4. Revised Implementation Plan

### Phase 0: Background Task Delegation

Before tackling the complexity of `call_agent`, we will first prove that we can successfully delegate a simpler, self-contained task to a background process. The `call_slm` tool is the perfect candidate for this. This phase will serve as a proof-of-concept for our background task delegation mechanism, akin to a JavaScript promise.

1.  **Implement the `subtask.py` resource adapter**.
2.  **Modify the `call_slm` tool** to run in the background and return a `subtask://` URI.
3.  **Implement the `get_task_status` tool**.

### Phase 1: The Minimal Viable Orchestrator

This phase will build upon the components developed in Phase 0. The `call_agent` tool will use the same `subtask://` resource and `get_task_status` tool that were developed for `call_slm`.

1.  **Implement the minimal `call_agent` tool**.

### Phase 2: Experimentation and Learning

1.  **Conduct a series of experiments** with different agent configurations and tasks.
2.  **Document the findings** in new `findings` documents.

### Phase 3: Heterogeneous Agents

1.  **Extend the `call_agent` tool** to allow for the configuration of the sub-agent's model, tools, and personality.
2.  **Implement the `agent_factory.py` module** and the shared `MCPClient`.

### Phase 4: Cross-Session Learning

1.  **Integrate the cross-session learning mechanisms** we have discussed, using `VectorMemory` as a knowledge base.

This phased approach will allow us to build a powerful and scalable orchestration system in a data-driven and iterative manner.
