# High Level Architecture

### Technical Summary

The Agent V2 platform is a **generic agent framework** enabling development of specialized agents through:

1. **ReAct Execution Engine**: Thought → Action → Observation loop with LLM-driven reasoning
2. **TodoList Planning**: Structured task decomposition with dependency tracking and acceptance criteria
3. **Extensible Tool System**: Base Tool class with async execution, validation, and retry logic
4. **Rich CLI Interface**: Typer-based modern CLI with 8 command groups and plugin extensibility
5. **State Persistence**: Async session state management with versioning and recovery
6. **Multi-Provider LLM Support**: LiteLLM integration for OpenAI, Anthropic, and other providers

### Platform Philosophy

> "Generic framework for agents of any kind" - supports RAG agents, generic problem-solving agents, domain-specific agents (finance, etc.)

Key design principles:
- **Agent specialization via system prompts**: Different agent types use different prompts and tool sets
- **Tool-first architecture**: Complex operations delegated to tools rather than inline code
- **Windows-first development**: PowerShell tools, Windows path handling, Unicode compatibility
- **Developer experience**: Rich CLI with auto-completion, progress bars, colored output
- **Extensibility**: Plugin architecture for third-party command groups and tool additions

### Actual Tech Stack

| Category              | Technology               | Version   | Notes                                          |
| --------------------- | ------------------------ | --------- | ---------------------------------------------- |
| Runtime               | Python                   | 3.11      | Required minimum version                       |
| Package Manager       | uv                       | latest    | NOT pip - all installs via `uv sync`           |
| LLM Orchestration     | LiteLLM                  | 1.7.7.0   | Multi-provider support (OpenAI, Anthropic)     |
| CLI Framework         | Typer                    | 0.9.0+    | Modern CLI with Rich integration               |
| Terminal UI           | Rich                     | 13.0.0+   | Colored output, tables, progress bars          |
| Async I/O             | aiofiles                 | 23.2.1    | Async file operations for state management     |
| Structured Logging    | structlog                | 24.2.0    | JSON/console logging with context              |
| Configuration         | Pydantic + Pydantic Settings | 2.0.0+ | Settings management with validation            |
| RAG Search            | Azure AI Search SDK      | 11.4.0+   | Semantic search and document retrieval         |
| Web Framework         | FastAPI                  | 0.116.1+  | Future web interface (not yet implemented)     |
| Testing               | pytest + pytest-asyncio  | 8.4.2+    | Unit and integration tests                     |

### Repository Structure Reality Check

- **Type**: Monorepo (single package with multiple modules)
- **Package Manager**: `uv` (NOT pip/venv)
- **Entry Points**: CLI commands defined in `pyproject.toml` [project.scripts]
- **Plugin System**: Entry points via `[project.entry-points."agent_cli_plugins"]`
- **Notable**: CLI is a first-class component (not an afterthought), sits alongside core agent code

---
