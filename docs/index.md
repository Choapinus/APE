# APE Documentation

Welcome to **APE (Agentic Protocol Executor)** – an open-source playground for building tool-using chat agents with the Model Context Protocol (MCP).

## High-level architecture

The live diagram in the repo-root `README.md` shows component relationships.

* **CLI shell** – curses-free text UI, minimal logic.
* **ChatAgent** – autonomous reasoning, tool routing, HMAC verification.
* **MCP server** – stateless JSON-RPC process exposing database/search/… tools.
* **Plugin registry** – `@tool` decorator + Python entry-points.
* **SQLite** – simple persistence for conversation history.
* **Ollama** – local LLM backend.

## Key features

| Feature | Status |
|---------|--------|
| Pydantic `Settings` | ✅ |
| HMAC-signed tool results | ✅ |
| Dynamic plugin system | ✅ |
| Typed request/response models | ✅ (core tools) |
| Async DB layer | 🚧 planned |

See the roadmap in the project board for upcoming work. 