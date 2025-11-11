# Source Tree and Module Organization

### Project Structure (Actual)

```
capstone/agent_v2/
├── agent.py                    # Main Agent class, MessageHistory, Action types, ReAct loop
├── tool.py                     # Base Tool abstract class with execute_safe() wrapper
├── statemanager.py             # StateManager for session persistence
├── conversation_manager.py     # (Appears unused - legacy?)
│
├── planning/
│   └── todolist.py             # TodoList, TodoItem, TodoListManager with LLM plan generation
│
├── tools/                      # All built-in tools
│   ├── code_tool.py            # PythonTool - ISOLATED NAMESPACE per execution (critical!)
│   ├── file_tool.py            # FileReadTool, FileWriteTool
│   ├── shell_tool.py           # PowerShellTool (Windows-focused)
│   ├── web_tool.py             # WebSearchTool, WebFetchTool
│   ├── git_tool.py             # GitTool, GitHubTool
│   ├── llm_tool.py             # LLMTool for text generation (used in RAG synthesis)
│   ├── azure_search_base.py    # Base class for Azure AI Search tools
│   ├── rag_semantic_search_tool.py    # Semantic search with Azure AI Search
│   ├── rag_list_documents_tool.py     # List documents with filtering
│   ├── rag_get_document_tool.py       # Get specific document details
│   └── ask_user_tool.py        # User interaction tool (appears unused?)
│
├── prompts/
│   ├── rag_system_prompt.py    # RAG_SYSTEM_PROMPT constant with tool selection logic
│   └── README.md               # Prompt engineering guidelines
│
├── cli/                        # Rich CLI interface (Typer-based)
│   ├── main.py                 # CLI entry point, app initialization, plugin setup
│   ├── plugin_manager.py       # Plugin discovery and loading via entry points
│   ├── output_formatter.py     # Multi-format output (table/JSON/YAML/text)
│   │
│   ├── commands/               # Command group implementations
│   │   ├── run.py              # Execute missions and tasks
│   │   ├── chat.py             # Interactive chat with agent
│   │   ├── missions.py         # Mission template management
│   │   ├── tools.py            # Tool discovery and management
│   │   ├── providers.py        # LLM provider configuration
│   │   ├── sessions.py         # Session management
│   │   ├── config.py           # Configuration management
│   │   ├── dev.py              # Developer/debug tools
│   │   └── rag.py              # RAG-specific commands
│   │
│   ├── config/
│   │   └── settings.py         # CLISettings with Pydantic validation
│   │
│   ├── plugins/                # Example plugin implementations
│   └── tests/                  # CLI unit tests
│
├── tests/                      # Core agent tests
│   ├── integration/            # Integration tests (RAG, synthesis)
│   └── unit/                   # Unit tests
│
├── docs/                       # Documentation
│   ├── prd.md                  # Rich CLI Tool PRD (v1.1)
│   ├── brownfield-architecture.md  # THIS DOCUMENT
│   └── rag_synthesis_example.py    # RAG synthesis reference implementations
│
├── pyproject.toml              # Package definition, dependencies, entry points
├── uv.lock                     # UV lock file (308KB - extensive dependency tree)
├── .env.example                # Environment variable template
├── README.md                   # RAG-focused README (multimodal synthesis)
└── CLAUDE.md                   # (Root) - Instructions for Claude Code agent
```

### Key Modules and Their Purpose

**Agent Core** (`agent.py`):
- `MessageHistory`: Rolling conversation window with system prompt preservation and compression
- `Agent` class: ReAct loop orchestrator with tool registry and message management
- `Agent.create_agent()`: Factory for generic agent with all standard tools
- `Agent.create_rag_agent()`: Factory for RAG agent with semantic search tools
- `Action` dataclass: Represents agent actions (tool_call, ask_user, complete, replan)

**Planning System** (`planning/todolist.py`):
- `TodoList`: Plan structure with items, open_questions, notes, todolist_id
- `TodoItem`: Task with description, acceptance_criteria, dependencies, status, chosen_tool, execution_result
- `TodoListManager`: LLM-based plan generation with JSON schema enforcement
- Persistence: Plans saved to `{work_dir}/todolists/{todolist_id}.json`

**Tool Framework** (`tool.py` + `tools/`):
- Base `Tool` class with abstract `execute()` method
- `execute_safe()` wrapper: validation, retry logic (max 3 attempts), timeout (60s), error handling
- `parameters_schema`: Auto-generated from method signature or manual override
- `function_tool_schema`: OpenAI function calling format
- **CRITICAL**: `PythonTool` uses **isolated namespace per execution** - variables DO NOT persist between calls

**CLI System** (`cli/`):
- Main app: 8 command groups (run, chat, missions, tools, providers, sessions, config, dev, rag)
- Plugin system: Discovers plugins via `agent_cli_plugins` entry point group
- Output formatting: Table (default), JSON, YAML, text modes
- Configuration: Hierarchical settings with env var overrides (`AGENT_` prefix)
- Entry points: `agent` (main CLI), `agent-dev` (developer CLI)

**RAG Capabilities**:
- Azure AI Search integration for semantic search
- Multimodal content retrieval (text + images)
- LLM-based synthesis via `LLMTool` (recommended) or programmatic via `PythonTool`
- Content blocks with citations: `(Source: filename.pdf, p. PAGE_NUMBER)`

---
