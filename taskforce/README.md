# Taskforce

Production-grade multi-agent orchestration framework built with Clean Architecture principles.

## Overview

Taskforce is a refactored and production-ready version of Agent V2, designed for enterprise deployment with:

- **Clean Architecture**: Strict layer separation (Core → Application → Infrastructure → API)
- **Protocol-based Design**: Swappable implementations for state management, LLM providers, and tools
- **Dual Interfaces**: CLI (Typer + Rich) and REST API (FastAPI)
- **Production Persistence**: PostgreSQL with SQLAlchemy for state management
- **RAG Capabilities**: Azure AI Search integration for semantic search
- **Docker Compose Deployment**: Self-hosted multi-container orchestration

## Architecture

```
taskforce/
├── src/taskforce/
│   ├── core/              # Domain logic (pure Python, no dependencies)
│   │   ├── domain/        # Agent, PlanGenerator, Domain Events
│   │   ├── interfaces/    # Protocols (StateManager, LLM, Tool)
│   │   └── prompts/       # System prompts and templates
│   ├── infrastructure/    # External integrations
│   │   ├── persistence/   # File and DB state managers
│   │   ├── llm/           # LiteLLM service (OpenAI, Azure)
│   │   ├── tools/         # Native, RAG, and MCP tools
│   │   └── memory/        # Memory management
│   ├── application/       # Use cases and orchestration
│   │   ├── factory.py     # Dependency injection
│   │   ├── executor.py    # Execution orchestration
│   │   └── profiles.py    # Configuration management
│   └── api/               # Entrypoints
│       ├── cli/           # Typer CLI
│       └── routes/        # FastAPI REST endpoints
├── tests/
│   ├── unit/              # Core domain tests
│   ├── integration/       # Infrastructure tests
│   └── fixtures/          # Test data and mocks
└── docs/                  # Architecture, PRD, stories
```

## Prerequisites

- **Python**: 3.11 or higher
- **Package Manager**: `uv` (not pip/venv)
- **Docker**: 24.0+ (for production deployment)
- **Docker Compose**: 2.23+ (for multi-container orchestration)

## Setup

### 1. Install uv

```powershell
# Windows (PowerShell)
pip install uv
```

### 2. Create Virtual Environment and Install Dependencies

```powershell
cd taskforce
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync
```

### 3. Configure Environment Variables

```powershell
# Copy example environment file
cp .env.example .env

# Edit .env and set required variables:
# - OPENAI_API_KEY (required for LLM calls)
# - GITHUB_TOKEN (optional, for GitHub API operations)
# - DATABASE_URL (for production PostgreSQL)
```

## Usage

### CLI Commands

```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

# Show help
taskforce --help

# Run a mission
taskforce run mission "Analyze sales data and create visualization"

# Interactive chat mode
taskforce chat

# List available tools
taskforce tools list

# Show tool details
taskforce tools inspect python

# List sessions
taskforce sessions list

# Show session details
taskforce sessions show <session-id>

# Show configuration
taskforce config show
```

### REST API

```powershell
# Start API server
uvicorn taskforce.api.server:app --reload --port 8000

# API Documentation
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

### Docker Compose Deployment

```powershell
# Start all services (API + PostgreSQL)
docker-compose up -d

# View logs
docker-compose logs -f taskforce

# Run database migrations
docker-compose exec taskforce alembic upgrade head

# Stop services
docker-compose down
```

## Development

### Run Tests

```powershell
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit

# With coverage
uv run pytest --cov=taskforce --cov-report=html

# View coverage report
start htmlcov/index.html
```

### Code Quality

```powershell
# Format code
uv run black src/taskforce tests

# Lint code
uv run ruff check src/taskforce tests

# Fix linting issues
uv run ruff check --fix src/taskforce tests

# Type checking
uv run mypy src/taskforce
```

### Project Structure

- **Core Layer**: Pure business logic, no external dependencies
- **Infrastructure Layer**: Implementations of protocols (DB, LLM, tools)
- **Application Layer**: Orchestration and dependency injection
- **API Layer**: CLI and REST interfaces

## Configuration Profiles

Taskforce supports multiple deployment profiles:

- **dev**: File-based state, local LLM, verbose logging
- **staging**: PostgreSQL state, cloud LLM, structured logging
- **prod**: PostgreSQL state, cloud LLM, JSON logging, monitoring

Profiles are loaded from `configs/{profile}.yaml` and can be overridden with environment variables.

## Key Features

### ReAct Agent Loop

1. **Load State**: Restore session from persistence
2. **Set Mission**: Define objective
3. **Create Plan**: Generate TodoList via LLM
4. **Execute Loop**: For each pending task:
   - Generate **Thought** (reasoning)
   - Execute **Action** (tool call, ask_user, replan, complete)
   - Record **Observation** (result)
   - Update state
5. **Complete**: All tasks resolved or mission achieved

### Available Tools

**Native Tools**:
- PythonTool: Execute Python code in isolated namespace
- FileReadTool / FileWriteTool: File system operations
- GitTool / GitHubTool: Git operations and GitHub API
- PowerShellTool: Shell command execution (Windows-first)
- WebSearchTool / WebFetchTool: HTTP requests and web scraping
- LLMTool: Nested LLM calls for sub-tasks
- AskUserTool: User interaction

**RAG Tools** (optional):
- SemanticSearchTool: Vector search in Azure AI Search
- ListDocumentsTool: Document listing with metadata
- GetDocumentTool: Document retrieval by ID

### State Management

- **Development**: File-based JSON state in `{work_dir}/states/`
- **Production**: PostgreSQL with JSONB columns for flexibility
- **Migration Path**: Protocol-based design enables seamless transition

## Relationship to Agent V2

Taskforce is a production refactoring of `capstone/agent_v2` with:

- **Clean Architecture**: Strict layer separation vs. mixed concerns
- **Production Persistence**: PostgreSQL vs. file-only
- **Dual Interfaces**: CLI + REST API vs. CLI-only
- **Protocol-based**: Swappable implementations vs. hardcoded
- **Docker Deployment**: Container-first vs. local-only

Agent V2 continues to function independently in `capstone/agent_v2` as the proof-of-concept.

## Contributing

1. Follow coding standards in `docs/architecture/coding-standards.md`
2. Write tests for all new functionality (≥90% coverage for core domain)
3. Use Black for formatting, Ruff for linting
4. Update documentation for API changes
5. Run full test suite before committing

## License

MIT License - see LICENSE file for details

## Support

- **Documentation**: See `docs/` directory
- **Architecture**: `docs/architecture.md`
- **PRD**: `docs/prd.md`
- **Stories**: `docs/stories/`

---

Built with ❤️ using Python 3.11, LiteLLM, FastAPI, and Clean Architecture principles.

