# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is an AI solution architecture repository containing coursework assignments and a capstone project. The primary focus is an IDP (Internal Developer Platform) Copilot prototype built as a ReAct agent.

## Project Structure

### Main Components

- **`capstone/`** - Main capstone project containing the IDP Copilot prototype
  - **`prototype/`** - Core ReAct agent implementation with tools and state management
  - **`backend/`** - FastAPI backend service
  - **`frontend/`** - Streamlit-based frontend application
  - **`examples/`** - Example implementations and CLI runners

- **`assignments/`** - Course assignments (assignment2-6) with individual requirements.txt files

### Key Files in Capstone Prototype

- `agent.py` - Main ReAct agent with plan-first heuristic and loop guard
- `tools.py` - Tool specification, normalization, execution, and indexing
- `tools_builtin.py` - Built-in tools for repository creation, CI/CD, K8s workflows
- `llm_provider.py` - LLM provider abstraction (OpenAI, Anthropic)
- `statemanager.py` - Session state persistence
- `todolist_md.py` - Markdown todo list creation and management
- `feedback_collector.py` - Feedback collection and storage

## Development Commands

### Environment Setup
```powershell
# Navigate to project root
Set-Location C:\Users\rudi\source\ai_solution_architecture

# Create virtual environment
uv venv .venv

# Activate (PowerShell)
. .\.venv\Scripts\Activate.ps1

# Install dependencies
uv pip install -r .\capstone\prototype\requirements.txt
```

### Running the Application
```powershell
# Main CLI entry point (starts Prometheus server on port 8070)
python .\capstone\prototype\idp.py

# Example IDP CLI runner
python .\capstone\examples\idp_pack\run_idp_cli.py

# Streamlit frontend
streamlit run .\capstone\frontend\streamlit_app.py
```

### Development Tools
```powershell
# Code formatting
uv run black .

# Linting
uv run ruff check .

# Type checking (if available)
uv run ruff format .

# Testing
uv run pytest -q
```

## Architecture

### ReAct Agent System
The core architecture follows a ReAct (Reasoning + Acting) pattern:

1. **Planning Phase** - Creates todo lists as markdown files in `./checklists`
2. **Tool Execution** - Executes tools via unified schema with alias/lookup index
3. **State Persistence** - Maintains session state in `./agent_states` (pickle files)
4. **Feedback Collection** - Stores feedback as JSON in `./feedback`
5. **Observability** - Prometheus metrics (port 8070) and optional OpenTelemetry traces

### Tool System
- Tools defined via `ToolSpec` with JSON schema validation
- Built-in tools include: repository creation, CI/CD setup, K8s deployment, documentation generation
- Tool normalization handles aliases and lookup by name
- Execution includes retry/backoff and circuit breaker patterns

### LLM Provider Abstraction
- Supports OpenAI and Anthropic providers
- Configurable via environment variables
- Structured output with Pydantic models

## Required Environment Variables

- `OPENAI_API_KEY` - Required for OpenAI provider
- `GITHUB_TOKEN` - Optional, for GitHub repository operations
- `GITHUB_ORG`/`GITHUB_OWNER` - Optional, target organization for GitHub repos
- `IDP_ENABLE_OTEL_CONSOLE` - Optional, enables OpenTelemetry console exporter

## Code Style Guidelines

Based on `.cursor/rules/python_coding_rules.mdc`:
- PEP8 compliant code with English variable names
- Functional programming preferred over classes
- Functions max 30 lines with docstrings and type annotations
- Use Black and Ruff for formatting and linting
- Write unit tests in separate `tests/` directory
- No sensitive data in code

## Development Notes

- The project assumes Windows PowerShell environment
- Uses `uv` for Python package management
- Git integration required for repository tools
- State files and outputs are created in local directories during agent execution
- Prometheus metrics available at `http://localhost:8070` when CLI is running