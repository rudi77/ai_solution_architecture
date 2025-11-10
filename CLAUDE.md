# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Windows-based AI solution architecture playground containing:
- **capstone/agent_v2**: A ReAct-style execution agent with TodoList planning, state management, and tool execution
- **assignments/**: ML/AI coursework (notebooks, MLflow artifacts) serving as sample workloads
- Python package management via `uv` (not pip/venv)

## Development Environment

**Platform**: Windows 10/11 with PowerShell 7+
**Python**: 3.11 managed by `uv`
**Package Manager**: `uv` (not pip)

### Environment Setup

Always work from `capstone/agent_v2` directory:
```powershell
cd capstone/agent_v2
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync
```

Required environment variables:
- `OPENAI_API_KEY` (required for LLM calls)
- `GITHUB_TOKEN` (optional, for GitHub API operations)

## Build and Test Commands

### Run Tests
```powershell
# From capstone/agent_v2 with venv active:

# CLI tests
uv run -m pytest .\cli\tests -q

# Core/unit tests (in repo root)
.\.venv\Scripts\python.exe -m pytest ..\..\tests -q
```

### Run the Agent

```powershell
# Via CLI (after uv sync)
agent --help
agent tools list
agent missions list
agent run mission <mission-name>

# Debug entrypoint (single file execution)
uv run python .\capstone\agent_v2\agent.py
```

## Architecture Overview

### ReAct Agent Flow

The agent follows a **ReAct (Reason + Act) loop**:
1. **Load State**: Restore session state from disk
2. **Set Mission**: Define objective on first call
3. **Create/Load Plan**: Generate TodoList using LLM
4. **Execute Loop**: For each pending TodoItem:
   - Generate **Thought** (rationale + action decision)
   - Execute **Action** (tool call, ask_user, replan, or complete)
   - Record **Observation** (success/failure + result data)
   - Update state and persist
5. **Complete**: All TodoItems resolved or mission goal achieved

### Core Components

**Agent Class** (`agent.py`):
- Main orchestrator implementing ReAct loop
- Manages MessageHistory (system prompt + rolling conversation window)
- Coordinates TodoListManager, StateManager, and Tools
- Two factory methods:
  - `Agent.create_agent()`: General-purpose agent with web/git/shell/python/file tools
  - `Agent.create_rag_agent()`: RAG-enabled agent with semantic search + document tools

**TodoListManager** (`planning/todolist.py`):
- LLM-based plan generation from mission text
- TodoItem structure: position, description, acceptance_criteria, dependencies, status, chosen_tool, execution_result
- TaskStatus: PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
- Plans persisted to `{work_dir}/todolists/{todolist_id}.json`

**StateManager** (`statemanager.py`):
- Session state persistence (answers, pending_question, todolist_id)
- Files stored in `{work_dir}/states/{session_id}.json`

**MessageHistory** (`agent.py:73-165`):
- Rolling conversation window (system prompt + last N message pairs)
- Auto-compression when exceeding SUMMARY_THRESHOLD
- Always includes system prompt as first message

**Tools** (`tools/`):
- Base class: `Tool` with `name`, `description`, `parameters_schema`, `execute()` method
- Built-in: WebSearchTool, WebFetchTool, PythonTool, GitTool, GitHubTool, FileReadTool, FileWriteTool, PowerShellTool, LLMTool
- RAG-specific: SemanticSearchTool, ListDocumentsTool, GetDocumentTool (using Azure AI Search)

### Action Types

- `tool_call`: Execute a tool with parameters
- `ask_user`: Pause execution and request user input
- `complete`: Finish execution with summary
- `replan`: Adjust TodoList (mark step skipped/failed)

### Python Tool Isolation

**CRITICAL**: Each Python tool execution runs in an **isolated namespace**. Variables from previous steps do NOT persist. The agent handles this via:
1. Pass data through `context` parameter (simple data)
2. Re-read from source files (CSV, JSON, etc.)
3. Error recovery with hints on retry attempts

## Code Style Rules (from .cursor/rules/python_coding_rules.mdc)

- PEP8-compliant code
- English variable names (descriptive, e.g., `user_count`, `is_valid`)
- Prefer functional/declarative programming; avoid classes when possible
- Functions ≤30 lines
- Docstrings required for all functions/modules
- Type annotations for all function signatures
- Use Black and Ruff for formatting/linting
- Unit tests in separate `tests/` directory
- Targeted exception handling with helpful error messages
- Never hardcode sensitive data
- Project structure: `src/` for source, `tests/` for tests, `docs/` for docs, `config/` for config

## CLI Plugin System

The CLI (`cli/main.py`) uses Typer + Rich for a structured command interface:
- Entry point: `agent` command (defined in pyproject.toml)
- Commands: `chat`, `run`, `missions`, `tools`, `providers`, `sessions`, `rag`, `config`, `dev`
- Plugin manager (`cli/plugin_manager.py`) loads plugins via entry points

## RAG Agent Capabilities

The RAG agent (`Agent.create_rag_agent()`) is designed for enterprise document Q&A:
- Uses Azure AI Search for semantic search
- Security filtering via `user_context` (user_id, org_id, scope)
- Tools: SemanticSearchTool, ListDocumentsTool, GetDocumentTool, LLMTool
- System prompt: `prompts/rag_system_prompt.py` with RAG-specific instructions

## Git Operations

- Git tools expect Windows-friendly `repo_path`
- GitHub remote constructed from `repo_full_name` when available
- Graceful fallback to `git remote set-url origin` if remote exists

## Troubleshooting

- **Command not found**: Re-run `uv sync` inside `capstone/agent_v2` and re-activate venv
- **LLM failures**: Verify `OPENAI_API_KEY` is set in current PowerShell session
- **Tool execution errors**: Check error type and hints in execution_result for retry logic
- **Python variable not found**: Remember isolated namespaces - re-read data or pass via context
