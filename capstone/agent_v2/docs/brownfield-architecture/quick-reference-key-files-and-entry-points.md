# Quick Reference - Key Files and Entry Points

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
