# Development and Deployment

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
