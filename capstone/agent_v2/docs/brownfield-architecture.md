# Agent V2 Platform - Brownfield Architecture Document

## Introduction

This document captures the **CURRENT STATE** of the Agent V2 platform, a Windows-based generic framework for building specialized AI agents. The platform supports multiple agent types (generic problem-solving, RAG knowledge retrieval, finance, etc.) through a ReAct-style execution engine with TodoList planning, tool execution, and state management.

**Document Scope**: Comprehensive documentation of the entire Agent V2 platform including core agent engine, CLI interface, tool framework, RAG capabilities, and infrastructure.

### Change Log

| Date       | Version | Description                       | Author  |
| ---------- | ------- | --------------------------------- | ------- |
| 2025-11-11 | 1.0     | Initial brownfield analysis       | Winston |

---

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

**Core Agent Engine**:
- **Main Agent Class**: `agent.py` - ReAct loop orchestrator, message history, agent factory methods
- **Tool Base**: `tool.py` - Abstract base class for all tools with validation and retry logic
- **State Management**: `statemanager.py` - Session state persistence with async file I/O and versioning

**Planning System**:
- **TodoList Manager**: `planning/todolist.py` - LLM-based plan generation, task status tracking, JSON persistence

**CLI Interface**:
- **CLI Entry Point**: `cli/main.py` - Typer-based CLI with 8 command groups and plugin system
- **Command Groups**: `cli/commands/*.py` - Individual command implementations (run, chat, missions, tools, providers, sessions, config, dev, rag)
- **Plugin Manager**: `cli/plugin_manager.py` - Plugin discovery via Python entry points
- **Output Formatter**: `cli/output_formatter.py` - Multi-format output rendering (table/JSON/YAML)
- **Settings**: `cli/config/settings.py` - Configuration management with environment variable overrides

**Tools** (all in `tools/`):
- **Core Tools**: `code_tool.py`, `file_tool.py`, `shell_tool.py`, `web_tool.py`, `git_tool.py`, `llm_tool.py`
- **RAG Tools**: `rag_semantic_search_tool.py`, `rag_list_documents_tool.py`, `rag_get_document_tool.py`
- **Azure Search Base**: `azure_search_base.py` - Shared Azure AI Search client logic

**System Prompts**:
- **Generic Agent**: `agent.py:25-58` - GENERIC_SYSTEM_PROMPT constant
- **RAG Agent**: `prompts/rag_system_prompt.py` - RAG-specific tool selection and synthesis instructions

**Configuration**:
- **Package Definition**: `pyproject.toml` - Dependencies, CLI entry points, plugin registration
- **Environment**: `.env.example` - Required environment variables template

### Current Enhancement Focus

**Rich CLI Tool PRD** (`docs/prd.md`): Transform CLI from basic interface to modern Typer-based rich experience with plugin architecture, progress visualization, and hierarchical configuration.

**Status**: CLI infrastructure is **substantially implemented** - all 8 command groups exist, plugin system operational, output formatting complete.

---

## High Level Architecture

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

## Source Tree and Module Organization

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

## Core Agent Architecture

### ReAct Execution Loop

The agent follows this flow (per CLAUDE.md):

```
1. Load State: Restore session from disk via StateManager
2. Set Mission: Define objective (if first run)
3. Create/Load Plan: Generate TodoList using TodoListManager
4. Execute Loop: For each pending TodoItem:
   a. Generate Thought (rationale + action decision)
   b. Execute Action (tool_call, ask_user, replan, or complete)
   c. Record Observation (success/failure + result data)
   d. Update state and persist to disk
5. Complete: All TodoItems resolved or mission goal achieved
```

**Key Files**:
- Main loop: `agent.py:Agent.run()` method (estimated around line 300-500 based on file size)
- State persistence: After each action via `StateManager.save_state()`
- Message management: `MessageHistory` maintains rolling window (last N message pairs)

### Message History Management

**Location**: `agent.py:73-165`

**Behavior**:
- Always includes system prompt as first message
- Rolling window of last N message pairs (user + assistant)
- Auto-compression when exceeding `SUMMARY_THRESHOLD` (40 messages)
- Compression uses LLM to summarize old context (model: gpt-4.1)
- Fallback: If compression fails, keeps recent messages only

**Critical Details**:
- MAX_MESSAGES = 50 pairs
- SUMMARY_THRESHOLD = 40 pairs
- `get_last_n_messages(n)`: Returns system prompt + last n complete pairs
- `n=-1`: Returns all messages (no truncation)

### TodoList Planning System

**Location**: `planning/todolist.py`

**Structure**:
```python
TodoList:
  - todolist_id: str (UUID)
  - items: List[TodoItem]
  - open_questions: List[str]  # Questions requiring user input
  - notes: str                 # Additional context

TodoItem:
  - position: int
  - description: str
  - acceptance_criteria: str   # "What done looks like" not "how to do it"
  - dependencies: List[int]    # Depends on TodoItem positions
  - status: TaskStatus         # PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
  - chosen_tool: Optional[str]
  - tool_input: Optional[Dict]
  - execution_result: Optional[Dict]
  - attempts: int (max 3)
```

**Plan Generation**:
- TodoListManager uses LLM with strict JSON schema
- Prompt includes available tools, their schemas, and mission description
- LLM generates minimal, deterministic plan with clear acceptance criteria
- Supports "ASK_USER" placeholders for missing parameters
- Plans persisted as JSON to `{work_dir}/todolists/{todolist_id}.json`

### State Persistence

**Location**: `statemanager.py`

**Features**:
- Async file I/O via `aiofiles`
- State stored as pickled dict: `{work_dir}/states/{session_id}.pkl`
- Versioning: `_version` incremented on each save, `_updated_at` timestamp
- Async locks per session to prevent race conditions
- Cleanup: `cleanup_old_states(days=7)` removes old sessions

**State Structure**:
```python
{
  "session_id": str,
  "todolist_id": Optional[str],
  "mission": str,
  "answers": Dict[str, Any],      # User responses to open_questions
  "pending_question": Optional[str],
  "_version": int,
  "_updated_at": str (ISO timestamp)
}
```

---

## Tool Framework Architecture

### Base Tool Interface

**Location**: `tool.py:10-168`

**Abstract Methods**:
- `name` (property): Tool identifier
- `description` (property): Natural language description
- `execute(**kwargs)`: Async method returning `Dict[str, Any]`

**Provided Methods**:
- `parameters_schema`: Auto-generated from `execute()` signature or manual override
- `function_tool_schema`: OpenAI function calling format
- `execute_safe()`: Robust wrapper with validation, retry, timeout, error handling
- `validate_params()`: Check required parameters before execution

**Execution Safety**:
- Max 3 retry attempts with exponential backoff (2^attempt seconds)
- 60-second timeout per execution
- Validation of parameters against signature
- Validation of return type (must be dict with "success" field)
- Comprehensive error capture with traceback

### Built-in Tools

#### PythonTool (`tools/code_tool.py`)

**CRITICAL DESIGN CONSTRAINT**: Each execution runs in an **isolated namespace**. Variables from previous steps DO NOT persist.

**Available Imports** (pre-imported):
- Standard: `os, sys, json, re, pathlib, shutil, subprocess, datetime, time, random, base64, hashlib, tempfile, csv`
- Optional: `pandas as pd, matplotlib.pyplot as plt` (if installed)
- Types: `Dict, List, Any, Optional`

**Context Handling**:
- Pass data via `context` dict parameter
- Context keys exposed as top-level variables in execution namespace
- Code must assign final output to `result` variable

**Working Directory**:
- Supports `cwd` parameter for path-relative operations
- Windows path handling (backslash conversion, quote stripping, expandvars)
- Validation: Checks if cwd exists and is directory before execution

**Error Recovery** (from CLAUDE.md):
> Agent handles namespace isolation via:
> 1. Pass data through context parameter (simple data)
> 2. Re-read from source files (CSV, JSON, etc.)
> 3. Error recovery with hints on retry attempts

#### FileReadTool & FileWriteTool (`tools/file_tool.py`)

- Basic file I/O operations
- **Note**: Implementation details not fully reviewed, check source for specifics

#### PowerShellTool (`tools/shell_tool.py`)

- **Windows-focused**: Executes PowerShell commands
- Used for Windows system operations, git commands, etc.
- **Platform dependency**: Will NOT work on Linux/Mac without modification

#### WebSearchTool & WebFetchTool (`tools/web_tool.py`)

- Web search and content fetching
- Details in source file

#### GitTool & GitHubTool (`tools/git_tool.py`)

- Git operations via PowerShell
- GitHub API operations (requires `GITHUB_TOKEN` environment variable)
- Windows path handling for `repo_path` parameters

#### LLMTool (`tools/llm_tool.py`)

**Purpose**: Natural language text generation (distinct from agent's own LLM calls)

**Use Cases**:
- RAG synthesis: Combining search results into cohesive responses
- Content generation within agent workflows
- Summary generation

**Parameters**:
- `prompt`: The generation prompt
- `context`: Additional context dict (optional)
- LLM model/temperature inherited from agent config or specified

#### RAG Tools (`tools/rag_*.py`)

**Base**: `azure_search_base.py` - Shared Azure AI Search client configuration

**SemanticSearchTool** (`rag_semantic_search_tool.py`):
- Input: `{"query": str, "top_k": int}`
- Output: List of content blocks (text + images) with relevance scores
- Returns: `block_id, block_type, content_text, image_url, image_caption, document_id, document_title, page_number, score`

**ListDocumentsTool** (`rag_list_documents_tool.py`):
- Input: `{"filters": dict, "limit": int}`
- Output: List of document metadata
- Filters: document_type, date_range, author, keywords

**GetDocumentTool** (`rag_get_document_tool.py`):
- Input: `{"document_id": str}`
- Output: Complete document metadata and summary

### Tool Registration

**Generic Agent**:
```python
tools = [
    PythonTool(),
    FileReadTool(),
    FileWriteTool(),
    PowerShellTool(),
    WebSearchTool(),
    WebFetchTool(),
    GitTool(),
    GitHubTool(),
    LLMTool()
]
```

**RAG Agent**:
```python
tools = [
    SemanticSearchTool(),
    ListDocumentsTool(),
    GetDocumentTool(),
    LLMTool(),
    PythonTool()  # For programmatic synthesis (optional)
]
```

---

## CLI System Architecture

### Command Structure

**Entry Point**: `cli/main.py:cli_main()`

**Main App** (`agent` command):
```
agent
├── run          # Execute missions/tasks
├── chat         # Interactive chat
├── missions     # Mission template management
├── tools        # Tool discovery/management
├── providers    # LLM provider configuration
├── sessions     # Session management
├── config       # Configuration management
├── dev          # Developer tools
└── rag          # RAG-specific commands
```

**Developer App** (`agent-dev` command):
- Separate entry point for debug features
- Same dev tools as main app but direct access

### Plugin Architecture

**Location**: `cli/plugin_manager.py`

**Discovery**:
- Uses Python entry points: `agent_cli_plugins` group
- Plugins register via `pyproject.toml`:
  ```toml
  [project.entry-points."agent_cli_plugins"]
  my-plugin = "package.plugins:MyPluginClass"
  ```

**Plugin Interface** (from CLI README):
```python
class CLIPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def command_group(self) -> typer.Typer: pass

    def setup(self, main_app: typer.Typer) -> None: pass
```

**Security**: TODO - Plugin validation not yet implemented (noted in PRD NFR5)

### Output Formatting

**Location**: `cli/output_formatter.py`

**Formats**:
- `table` (default): Rich tables with colored headers
- `json`: Machine-readable JSON output
- `yaml`: Human-readable YAML
- `text`: Plain text (for piping)

**Usage**: All list commands support `--output <format>` flag

### Configuration Management

**Location**: `cli/config/settings.py`

**Features**:
- Pydantic-based settings with validation
- Environment variable overrides (prefix: `AGENT_`)
- File-based persistence (default: `~/.agent/config.yaml`)
- Hierarchical settings (user > system > defaults)

**Key Settings** (from CLI README):
- `default_provider`: LLM provider ID
- `default_output_format`: CLI output format
- `tool_discovery_paths`: Paths to search for tools
- `session_cleanup_days`: Auto-cleanup threshold
- `debug_mode`: Enable debug logging

### Command Implementation Status

**Fully Implemented** (based on file analysis):
- ✅ **run**: Execute missions and tasks
- ✅ **chat**: Interactive agent chat (21KB file - substantial implementation)
- ✅ **missions**: Mission template management
- ✅ **tools**: Tool discovery and management
- ✅ **providers**: LLM provider configuration
- ✅ **sessions**: Session management
- ✅ **config**: Configuration management
- ✅ **dev**: Developer tools
- ✅ **rag**: RAG commands (14KB file - recent addition)

**Notes**:
- CLI PRD describes 35+ individual commands across these groups
- Each command file is 6-21KB suggesting substantial (not stub) implementations
- CLI README shows comprehensive examples for all command groups

---

## RAG System Architecture

### Overview

RAG capabilities enable enterprise document Q&A through Azure AI Search integration. System supports:
- Multimodal content retrieval (text + images)
- Semantic search with relevance scoring
- Document metadata search and filtering
- LLM-based content synthesis with citations

### RAG Agent Specialization

**Factory Method**: `Agent.create_rag_agent()` in `agent.py`

**System Prompt**: `prompts/rag_system_prompt.py:24-300+` (14KB file)

**Prompt Focus**:
- Tool selection expertise (which tool for which query type)
- Query classification (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON, AUTONOMOUS_WORKFLOW)
- Synthesis guidance (combining multimodal results with citations)
- **NOT planning** - planning handled by Agent orchestrator

### Multimodal Synthesis Workflow

**Standard Pattern** (from README.md):
```
User Query: "How does the XYZ pump work?"
    ↓
Step 1: Semantic Search (rag_semantic_search)
    Returns: List of text + image content blocks with metadata
    ↓
Step 2: Synthesize Response (llm_generate OR python_tool)
    Returns: Cohesive markdown with embedded images and citations
    ↓
Output: Markdown with text + ![images] + (Source: file, p. N)
```

**Synthesis Approaches**:

1. **LLM-based (Recommended)**: Use `LLMTool`
   - Pros: Natural narrative flow, context understanding, simpler
   - Cons: LLM cost for synthesis step

2. **Programmatic**: Use `PythonTool` with generated code
   - Pros: Precise formatting, deterministic, no LLM cost
   - Cons: More complex, requires code generation

### Content Block Structure

**Returned by SemanticSearchTool**:
```python
{
    "block_id": "unique-id",
    "block_type": "text" | "image",
    "content_text": "...",          # If text block
    "image_url": "...",              # If image block
    "image_caption": "...",          # If image block
    "document_id": "...",
    "document_title": "filename.pdf",
    "page_number": 12,
    "chunk_number": 5,
    "score": 0.85                    # Relevance score (0.0-1.0)
}
```

### Citation Format

**Standard** (enforced by RAG system prompt):
```markdown
The XYZ pump operates using a centrifugal mechanism...

*(Source: technical-manual.pdf, p. 45)*

![Diagram showing XYZ pump components](https://storage.example.com/diagram.jpg)

*(Source: technical-manual.pdf, p. 46)*
```

### Azure AI Search Configuration

**Environment Variables** (required):
- `AZURE_SEARCH_ENDPOINT`: `https://your-search.search.windows.net`
- `AZURE_SEARCH_KEY`: API key
- `AZURE_SEARCH_INDEX`: Index name

**Security Filtering** (mentioned in README):
- `user_context` parameter: `{user_id, org_id, scope}`
- Filters search results by user permissions
- Implementation in `azure_search_base.py`

---

## Integration Points and External Dependencies

### LLM Providers

**Integration**: LiteLLM library (version 1.7.7.0)

**Supported Providers**:
- OpenAI (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- Anthropic (claude models)
- Others via LiteLLM's unified interface

**Configuration**:
- Provider credentials via environment variables (e.g., `OPENAI_API_KEY`)
- Model selection per agent instance
- Default provider managed via CLI `providers` commands

**Model Usage**:
- Agent reasoning: User-specified model (e.g., "gpt-4")
- Message compression: Hardcoded "gpt-4.1" in `MessageHistory.compress_history_async()`
- Tool generation (LLMTool): Inherits from agent config or overridable

### Azure AI Search

**Integration**: Azure Search Documents SDK (11.4.0+)

**Purpose**: RAG knowledge retrieval backend

**Connection**:
- Endpoint, key, and index name via environment variables
- Shared client in `tools/azure_search_base.py`
- Used by SemanticSearchTool, ListDocumentsTool, GetDocumentTool

**Index Schema** (inferred from content blocks):
- Text chunks with embeddings
- Image metadata with captions and URLs
- Document metadata (title, page numbers, chunk numbers)
- Security metadata for filtering

### External Services

| Service      | Purpose                      | Integration Type | Key Files/Config                     |
| ------------ | ---------------------------- | ---------------- | ------------------------------------ |
| OpenAI       | LLM reasoning & generation   | REST API         | OPENAI_API_KEY env var               |
| Azure Search | RAG semantic search          | SDK              | AZURE_SEARCH_* env vars              |
| GitHub       | Git operations (optional)    | REST API         | GITHUB_TOKEN env var                 |
| Web          | Search and fetch (via tools) | HTTP             | WebSearchTool, WebFetchTool          |

### File System Dependencies

**State Storage**:
- Default: `./agent_states/{session_id}.pkl`
- Configurable via StateManager constructor

**TodoList Storage**:
- Default: `{work_dir}/todolists/{todolist_id}.json`
- Work directory specified per agent/session

**CLI Configuration**:
- Default: `~/.agent/config.yaml`
- Environment override: `AGENT_CONFIG_PATH`

**Session Logs**:
- Mentioned in CLI commands but location TBD (check dev/logs implementation)

---

## Development and Deployment

### Local Development Setup

**Platform**: Windows 10/11 with PowerShell 7+

**Steps** (from CLAUDE.md):
```powershell
# 1. Navigate to agent_v2
cd capstone/agent_v2

# 2. Create virtual environment via uv
uv venv .venv

# 3. Activate venv
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
uv sync

# 5. Set environment variables
# Edit .env file or set in PowerShell session:
$env:OPENAI_API_KEY = "your-key"
$env:GITHUB_TOKEN = "your-token"  # Optional

# 6. Verify installation
agent --help
```

**Known Setup Issues**:
- Must use `uv` not `pip` - pip installations will fail
- Virtual environment MUST be activated before running commands
- Environment variables must be set in active PowerShell session or .env file

### Running the Agent

**Via CLI** (recommended):
```powershell
# List available commands
agent --help

# Execute a mission
agent run mission <mission-name>

# Interactive chat
agent chat

# List tools
agent tools list
```

**Direct Execution** (debug):
```powershell
# Single-file execution for debugging
uv run python .\capstone\agent_v2\agent.py
```

### Testing

**Test Structure**:
- Unit tests: `tests/` in agent_v2 root
- CLI tests: `cli/tests/`
- Integration tests: `tests/integration/`

**Running Tests** (from CLAUDE.md):
```powershell
# From capstone/agent_v2 with venv active:

# CLI tests
uv run -m pytest .\cli\tests -q

# Core/unit tests (run from repo root)
.\.venv\Scripts\python.exe -m pytest tests -q
```

**Test Coverage**:
- RAG synthesis: `tests/integration/test_rag_synthesis.py`
- Other integration tests in `tests/integration/`
- Coverage metrics not documented

### Build and Deployment

**Package Build**:
- Package name: `hybrid-agent` (from pyproject.toml)
- Version: 0.1.0
- Build: Standard Python package (`pip install -e .` or `uv sync`)

**Entry Points**:
- `agent`: Main CLI (`cli.main:cli_main`)
- `agent-dev`: Developer CLI (`cli.main:dev_main`)

**Deployment**:
- No deployment scripts found in repository
- Likely manual installation per environment
- FastAPI dependency suggests future web deployment (not yet implemented)

### Environment Variables

**Required**:
- `OPENAI_API_KEY`: OpenAI API access (or other LLM provider key)

**Optional**:
- `GITHUB_TOKEN`: GitHub API operations
- `AZURE_SEARCH_ENDPOINT`: RAG search endpoint
- `AZURE_SEARCH_KEY`: RAG search API key
- `AZURE_SEARCH_INDEX`: RAG index name
- `AGENT_DEBUG`: Enable debug logging
- `AGENT_*`: Any CLI config setting (e.g., `AGENT_DEFAULT_PROVIDER`)

**Windows-Specific**:
- `PYTHONIOENCODING=utf-8`: Set automatically by CLI main.py for Unicode support

---

## Technical Debt and Known Issues

### Critical Technical Debt

#### 1. PythonTool Isolated Namespace

**Location**: `tools/code_tool.py`

**Issue**: Each PythonTool execution runs in an isolated namespace. Variables from previous steps DO NOT persist.

**Impact**:
- Agent must re-read data from files or pass via context on each call
- Increases complexity of multi-step data processing workflows
- Can cause confusion for AI agents unfamiliar with this constraint

**Workarounds** (from CLAUDE.md):
1. Pass data through `context` parameter for simple data
2. Re-read from source files (CSV, JSON) on each step
3. Agent provides hints on retry attempts after failures

**Why This Design**:
- Security: Prevents unintended side effects between executions
- Isolation: Each tool call is independent and testable
- Clean state: No accumulated globals or stale state

**Future Options**:
- Document prominently in tool description
- Add session-scoped namespace option (with explicit opt-in)
- Provide helper for persisting variables to temp files

#### 2. Windows Platform Dependency

**Issue**: PowerShellTool and various path-handling logic assumes Windows environment.

**Impact**:
- Agent platform not portable to Linux/Mac without modifications
- Tool: PowerShellTool will fail on non-Windows
- Paths: Backslash handling in file operations

**Files Affected**:
- `tools/shell_tool.py`: PowerShellTool uses Windows PowerShell
- `tools/code_tool.py`: Windows path normalization (line 60-62)
- `cli/main.py`: Windows Unicode handling (lines 24-30)

**Future Options**:
- Detect platform and use Bash/Zsh on Linux/Mac
- Unified shell tool with platform abstraction
- Pathlib usage consistently (already used in some places)

#### 3. Plugin Security Not Implemented

**Issue**: CLI plugin validation mentioned in PRD NFR5 not yet implemented.

**Location**: `cli/plugin_manager.py` - validation is TODO

**Risk**: Malicious plugins could execute arbitrary code when loaded via entry points.

**Future Requirements**:
- Plugin signature verification
- Sandboxed plugin execution
- Permission system for plugin capabilities

#### 4. Message Compression Model Hardcoded

**Location**: `agent.py:106-110` - Uses "gpt-4.1" for compression

**Issue**: Model name hardcoded instead of configurable or using agent's model.

**Impact**:
- Cannot use different provider for compression
- "gpt-4.1" may not exist in all LiteLLM configurations
- Cost optimization not possible (compression could use cheaper model)

**Future Fix**:
- Use agent's configured model or separate configurable compression model
- Add fallback logic if model unavailable

### Workarounds and Gotchas

#### Unicode Handling on Windows

**Issue**: Windows console encoding issues with Unicode

**Workaround** (implemented in `cli/main.py:24-30`):
```python
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
```

**Why Needed**: Windows console defaults to CP1252 encoding, breaks Rich output

#### TodoList JSON Schema Errors

**Issue**: LLM sometimes returns invalid JSON or wrong structure

**Workaround** (implemented in `todolist.py:89-127`):
- Graceful parsing with fallbacks to empty defaults
- Status string normalization (e.g., "inprogress" → IN_PROGRESS)
- Position defaults to index if missing

**Best Practice**: Use strict schema in prompt with examples

#### State Persistence Race Conditions

**Issue**: Multiple async operations could corrupt state file

**Workaround** (implemented in `statemanager.py:23-27`):
- Async lock per session_id
- Get-or-create pattern for locks
- State operations always wrapped in `async with lock`

#### Git Tool Windows Paths

**Issue**: Git expects forward slashes, Windows uses backslashes

**Workaround**: (Check `git_tool.py` implementation - not fully reviewed)

---

## CLI Enhancement Status (PRD vs. Reality)

### PRD Requirements Overview

**Document**: `docs/prd.md` (v1.1, dated 2025-01-18)

**Goals**:
- Replace minimal argparse CLI with Typer-based rich interface
- Implement 7 core command groups + dev tools (8 total)
- Plugin architecture via entry points
- Rich interactive experience (progress bars, colored tables, multi-format output)
- Hierarchical configuration management
- Backward compatibility with existing agent execution

### Implementation Status

#### Functional Requirements

| Requirement | Status | Notes                                                   |
| ----------- | ------ | ------------------------------------------------------- |
| FR1: 8 command groups | ✅ DONE | run, chat, missions, tools, providers, sessions, config, dev, rag (9 total - rag added) |
| FR2: Auto-completion | ❓ UNKNOWN | Typer supports it, but shell integration setup not verified |
| FR3: Plugin discovery | ✅ DONE | PluginManager with entry points implemented |
| FR4: Progress visualization | 🟡 PARTIAL | Rich library integrated, usage in long-running commands TBD |
| FR5: Multi-format output | ✅ DONE | OutputFormatter with table/JSON/YAML/text |
| FR6: Interactive parameter collection | 🟡 PARTIAL | Typer prompts available, mission-specific logic TBD |
| FR7: Session management | ✅ DONE | sessions command group with list/show/resume/export |
| FR8: Hierarchical config | ✅ DONE | CLISettings with file + env var overrides |
| FR9: Interactive shell mode | ❓ UNKNOWN | dev shell command exists, functionality TBD |
| FR10: Comprehensive help | ✅ DONE | Typer auto-generates help, custom descriptions in commands |
| FR11: Mission template management | ✅ DONE | missions command group implemented |
| FR12: Tool management | ✅ DONE | tools command group implemented |
| FR13: Provider management | ✅ DONE | providers command group implemented |
| FR14: Developer/debug features | ✅ DONE | dev command group with logs/debug/version |
| FR15: Backward compatibility | ✅ DONE | Existing Agent.run() interface unchanged |

#### Non-Functional Requirements

| Requirement | Status | Notes                                                   |
| ----------- | ------ | ------------------------------------------------------- |
| NFR1: Startup <200ms | ❓ UNKNOWN | Not measured, should benchmark |
| NFR2: Graceful error handling | ✅ DONE | Rich tracebacks, structured errors |
| NFR3: Input validation | ✅ DONE | Pydantic settings, Typer validation |
| NFR4: Cross-platform | 🔴 NO | Windows-focused (PowerShellTool, path handling) |
| NFR5: Plugin security | 🔴 NO | Validation not implemented (TODO in code) |
| NFR6: Accessibility | 🟡 PARTIAL | Rich uses colors, screen reader support unknown |
| NFR7: Human-readable config | ✅ DONE | YAML format, inline docs via Pydantic |
| NFR8: Consistent command structure | ✅ DONE | All commands follow Typer conventions |
| NFR9: Exit codes | ❓ UNKNOWN | Check main.py exception handling |
| NFR10: Interactive + batch modes | 🟡 PARTIAL | Interactive works, batch mode (--batch flag) TBD |

### What Remains for Full PRD Compliance

**High Priority**:
1. ❌ **Cross-platform support** (NFR4): Implement Bash alternative to PowerShellTool
2. ❌ **Plugin security** (NFR5): Add validation, sandboxing, signatures
3. ❌ **Startup performance benchmark** (NFR1): Measure and optimize if needed

**Medium Priority**:
4. 🟡 **Progress bars in long operations** (FR4): Audit run/chat commands for progress display
5. 🟡 **Interactive shell mode** (FR9): Verify dev shell implementation completeness
6. 🟡 **Batch mode** (NFR10): Test and document --batch flag behavior
7. 🟡 **Auto-completion setup** (FR2): Document shell integration steps

**Low Priority**:
8. ❓ **Exit codes standardization** (NFR9): Document and standardize exit codes
9. ❓ **Accessibility testing** (NFR6): Test with screen readers

---

## Architecture Decision Records (Inferred)

### Why LiteLLM?

**Decision**: Use LiteLLM for LLM provider abstraction

**Rationale**:
- Unified interface across OpenAI, Anthropic, and other providers
- Easy provider switching without code changes
- Built-in retry and fallback logic
- Active maintenance and broad provider support

**Tradeoffs**:
- Additional dependency layer
- Provider-specific features may not be exposed
- Version 1.7.7.0 used (not latest) - may be stability vs features decision

### Why Typer + Rich for CLI?

**Decision**: Typer framework with Rich terminal formatting

**Rationale**:
- Modern Python CLI framework with type hints
- Auto-generated help and validation
- Rich provides beautiful terminal output (tables, progress bars, colors)
- Strong ecosystem and documentation

**Tradeoffs**:
- Larger dependency footprint than argparse
- Windows Unicode issues required workarounds
- Startup time potentially slower (NFR1 concern)

### Why TodoList Planning?

**Decision**: LLM-generated TodoList with structured tasks instead of free-form execution

**Rationale**:
- Provides structure and transparency (user can see plan before execution)
- Enables dependency tracking and parallel execution
- Facilitates state recovery (resume from interrupted sessions)
- Acceptance criteria define "done" independent of implementation

**Tradeoffs**:
- Additional LLM call for planning (cost + latency)
- LLM may generate suboptimal plans requiring replanning
- JSON schema enforcement can cause parsing errors

### Why Isolated PythonTool Namespace?

**Decision**: Each PythonTool execution uses fresh namespace

**Rationale**:
- Security: Prevents unintended side effects between executions
- Isolation: Each tool call is independent and testable
- Clean state: No accumulated globals or stale state

**Tradeoffs**:
- Cannot persist variables between executions
- Increases complexity of multi-step data processing
- Agent must re-read data or use context parameter

### Why Async State Persistence?

**Decision**: Async file I/O with locks for state management

**Rationale**:
- Non-blocking I/O for better performance
- Locks prevent race conditions in concurrent access
- Versioning enables optimistic concurrency control

**Tradeoffs**:
- More complex than synchronous file I/O
- Pickle format not human-readable (YAML would be better for debugging)

---

## Testing Reality

### Current Test Structure

**Test Directories**:
- `tests/` - Core agent tests (in agent_v2 root)
- `tests/integration/` - Integration tests (RAG, synthesis)
- `cli/tests/` - CLI unit tests

**Known Tests**:
- RAG synthesis: `tests/integration/test_rag_synthesis.py` (mentioned in README)
- CLI tests: Files exist in `cli/tests/` directory

**Running Tests**:
```powershell
# CLI tests
uv run -m pytest .\cli\tests -q

# Core tests (from repo root)
.\.venv\Scripts\python.exe -m pytest tests -q

# Integration tests
pytest tests/integration/ -v -k rag
```

### Test Coverage

**Unknown Areas**:
- Overall coverage percentage not documented
- Unit test completeness unclear
- Integration test scope unknown beyond RAG

**Best Practice** (from project guidelines):
- Tests required for all functions/modules
- Separate tests/ directory (✅ implemented)
- Targeted exception handling (presumably tested)

---

## Performance Considerations

### Startup Performance

**Target**: <200ms for simple commands (NFR1)

**Current Status**: Not measured

**Potential Issues**:
- Rich library import overhead
- Plugin discovery on startup
- Configuration file loading
- LiteLLM initialization

**Optimization Opportunities**:
- Lazy load plugins (only when needed)
- Cache configuration in memory
- Defer Rich imports to command execution
- Profile with `agent dev profile` command

### Memory Usage

**State Files**: Pickle format with versioning - size depends on message history length

**Considerations**:
- Message history compression after 40 message pairs
- TodoList JSON persistence (lightweight)
- Session cleanup after 7 days (configurable)

**Potential Issues**:
- Large state files if compression fails
- Memory leaks in long-running sessions (not verified)

### LLM Call Efficiency

**Current Pattern**:
- Plan generation: 1 LLM call per new mission
- Execution loop: 1 LLM call per TodoItem (thought + action decision)
- Message compression: 1 LLM call when threshold exceeded
- RAG synthesis: 1 additional LLM call (if using LLMTool approach)

**Optimization Opportunities**:
- Batch multiple TodoItem decisions (risky - less precise)
- Use cheaper models for compression
- Cache common plans (mission template system)

---

## Future Enhancements (Inferred)

### From PRD

**Planned Features** (not yet implemented):
- Interactive shell mode with session persistence
- Performance profiling commands
- Benchmark suite
- Integration tests via CLI

### From README

**RAG Enhancements**:
- Automatic image filtering (remove irrelevant diagrams)
- Content deduplication across sources
- Citation style customization (APA, MLA, etc.)
- Response length control with summarization
- Multi-language synthesis support
- Streaming synthesis for real-time updates

### Inferred from Architecture

**Platform Expansion**:
- Cross-platform support (Linux/Mac)
- Web interface (FastAPI dependency suggests this is planned)
- REST API for agent execution
- Mission template marketplace/registry

**Enterprise Features**:
- Multi-tenancy support
- Role-based access control (RBAC)
- Audit logging
- Cost tracking and optimization
- Team collaboration features

---

## Appendix - Useful Commands and Scripts

### Frequently Used Commands

```powershell
# Setup
cd capstone/agent_v2
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync

# CLI Operations
agent --help                              # Show all commands
agent tools list                          # List available tools
agent missions list                       # List mission templates
agent providers list                      # List LLM providers
agent sessions list                       # List recent sessions

# Execution
agent run mission <mission-name>          # Execute a mission
agent chat                                # Interactive chat mode
agent run task "Analyze logs for errors"  # Ad-hoc task

# Configuration
agent config show                         # Show current config
agent config set default_provider openai  # Update setting
agent config export backup.yaml           # Backup config

# Development
agent dev logs --follow                   # Tail logs
agent --verbose run mission <name>        # Verbose execution
uv run python agent.py                    # Direct execution (debug)

# Testing
uv run -m pytest .\cli\tests -q           # CLI tests
pytest tests/integration/ -v              # Integration tests
```

### Debugging and Troubleshooting

**Common Issues**:

1. **CLI not found**:
   ```powershell
   # Re-run uv sync and re-activate venv
   .\.venv\Scripts\Activate.ps1
   uv sync
   ```

2. **LLM failures**:
   ```powershell
   # Check environment variable
   echo $env:OPENAI_API_KEY
   # Set if missing
   $env:OPENAI_API_KEY = "your-key"
   ```

3. **Unicode errors** (Windows):
   ```powershell
   # Should be automatic in CLI, but for scripts:
   $env:PYTHONIOENCODING = 'utf-8'
   ```

4. **PythonTool variable not found**:
   - Remember: Isolated namespace per execution
   - Pass data via `context` parameter or re-read from files

**Debug Mode**:
```powershell
# Enable verbose output
agent --verbose <command>

# Enable debug logging
agent dev debug "<command>"
$env:AGENT_DEBUG = "true"

# View logs
agent dev logs --follow
```

### Development Workflow

**Making Changes**:
1. Edit files in agent_v2/
2. No rebuild needed (installed with `-e` flag)
3. Test changes: `uv run -m pytest`
4. Run CLI: `agent <command>`

**Adding a New Tool**:
1. Create tool class in `tools/` inheriting from `Tool`
2. Implement `name`, `description`, `execute()` methods
3. Register in `Agent.create_agent()` or specialized agent factory
4. Test with `agent tools list` and execution

**Adding a CLI Command**:
1. Edit appropriate command group in `cli/commands/`
2. Use Typer decorators for command definition
3. Test with `agent <group> <command> --help`

**Adding a Plugin**:
1. Create plugin package with CLIPlugin class
2. Register in package's `pyproject.toml` entry points
3. Install package: `uv pip install -e .`
4. Verify: `agent dev version --detailed`

---

## Document Metadata

**Generated**: 2025-11-11
**Agent**: Winston (Architect)
**Platform**: Windows 11, Python 3.11, UV package manager
**Codebase**: C:\Users\rudi\source\ai_solution_architecture\capstone\agent_v2
**Purpose**: Brownfield architecture documentation for AI agent development

**Key Contacts** (inferred):
- Project owner: rudi (from file paths)
- PRD author: John (PM) - from prd.md changelog

**Related Documents**:
- `README.md` - RAG-focused user guide
- `CLAUDE.md` - (Root) Instructions for Claude Code agent
- `docs/prd.md` - Rich CLI Tool Product Requirements Document v1.1
- `cli/README.md` - CLI subsystem documentation
- `prompts/README.md` - Prompt engineering guidelines

**Revision Policy**:
- Update this document when major architectural changes occur
- Maintain "Reality Check" sections with actual implementation status
- Document technical debt as discovered
- Keep example commands up-to-date with actual CLI behavior

---

**END OF DOCUMENT**
