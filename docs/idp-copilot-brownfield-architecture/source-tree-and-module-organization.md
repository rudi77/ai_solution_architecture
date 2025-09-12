# Source Tree and Module Organization

## Project Structure (Actual)

```text
capstone/
├── prototype/                    # Core ReAct agent implementation
│   ├── agent.py                 # Main ReAct agent with loop guard
│   ├── tools.py                 # Tool specification and execution
│   ├── tools_builtin.py         # Built-in IDP tools (repo, CI/CD, K8s)
│   ├── llm_provider.py          # OpenAI/Anthropic provider abstraction
│   ├── statemanager.py          # Session state persistence (pickle)
│   ├── todolist_md.py           # Markdown todo list rendering
│   ├── feedback_collector.py    # User feedback collection
│   └── idp.py                   # CLI entry point + Prometheus server
├── backend/                     # FastAPI web service
│   └── app/
│       ├── main.py              # FastAPI application factory
│       ├── api/                 # API route modules
│       │   ├── agent_systems.py # Agent configuration management
│       │   ├── sessions.py      # Session lifecycle API
│       │   ├── tools.py         # Tool management API
│       │   └── stream.py        # SSE streaming endpoints
│       ├── core/                # Core backend services
│       │   ├── builder.py       # Agent system builder
│       │   ├── registry.py      # Component registry
│       │   └── session_store.py # Session management
│       └── schemas/             # Pydantic data models
├── frontend/                    # Streamlit web interface
│   ├── streamlit_app.py         # Main Streamlit application
│   └── components/
│       └── sse_chat.py          # SSE chat component
├── examples/                    # Example CLI implementations
│   └── idp_pack/
│       ├── run_idp_cli.py       # Basic CLI runner
│       └── rich_idp_cli.py      # Rich CLI with enhanced UI
├── tests/                       # Integration and API tests
│   ├── test_api.py              # API endpoint tests
│   ├── test_e2e.py              # End-to-end workflow tests
│   └── test_artifacts.py       # Artifact generation tests
├── documents/                   # Project documentation
│   ├── prd.md                   # Product Requirements Document
│   ├── spec.md                  # Technical specifications
│   └── frontend_spec.md         # Frontend requirements
└── pyproject.toml               # Project configuration and dependencies
```

## Key Modules and Their Purpose

- **ReAct Agent Core** (`prototype/agent.py`): Main reasoning engine with plan-first heuristic and loop guard protection
- **Tool Ecosystem** (`prototype/tools.py`, `tools_builtin.py`): Unified tool interface with 15+ built-in IDP tools
- **State Management** (`prototype/statemanager.py`): Pickle-based session persistence with recovery
- **LLM Integration** (`prototype/llm_provider.py`): Provider abstraction supporting OpenAI and Anthropic
- **FastAPI Backend** (`backend/app/`): RESTful API with SSE streaming for real-time agent interaction
- **Streamlit Frontend** (`frontend/`): Demo UI with real-time chat and todo list visualization