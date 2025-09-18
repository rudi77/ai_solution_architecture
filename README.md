### AI Solution Architecture – Capstone Agent V2 and Assignments

This repository contains a practical AI solution architecture playground:

- **capstone/agent_v2**: A ReAct-style execution agent with a rich CLI, tool suite (web, git, shell, python, files), TodoList planning, and state management.
- **assignments/**: A collection of ML/AI coursework (notebooks, MLflow artifacts, small utilities) used as sample workloads and datasets.
- **examples/** and **templates/**: Prompt templates and project scaffolds.
- **tests/**: Unit tests for core components.

The project is designed for Windows and PowerShell. All setup and run instructions use `uv` for Python and package management.


## Prerequisites

- Windows 10/11 with PowerShell 7+
- `uv` (manages Python and dependencies). Install via PowerShell:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

- A Python 3.11 runtime managed by `uv`:

```powershell
uv python install 3.11
```

- Optional but recommended environment variables (depending on the tools you’ll use):
  - `OPENAI_API_KEY` for LLM access
  - `GITHUB_TOKEN` for GitHub API operations


## Project Structure

- `capstone/agent_v2/`: Agent framework package (installable via `uv sync`)
  - `agent.py`: Agent runtime with a minimal debug entrypoint
  - `cli/`: Rich Typer CLI (entry point command: `agent`)
  - `tools/`: Built-in tools (`git`, `github`, `python`, `file_read/write`, `powershell`, `web`)
  - `planning/`: TodoList manager and task orchestration
  - `pyproject.toml`: Project metadata and dependencies
- `assignments/`: Example datasets, notebooks, and small apps
- `examples/idp_pack/`: Example prompts and runner
- `templates/`: App scaffolding templates
- `tests/`: Unit tests for planning and history


## Setup (uv + virtual environment)

1) Create and activate a project virtual environment inside `capstone/agent_v2`:

```powershell
Set-Location .\capstone\agent_v2
uv venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install project dependencies (and register the CLI entry points):

```powershell
uv sync
```

3) Configure environment variables for your session:

```powershell
$env:OPENAI_API_KEY = "<your-openai-key>"
# Optional for GitHub-backed tools
$env:GITHUB_TOKEN = "<your-github-token>"
```


## Quick Start

### Use the CLI

After activating the venv inside `capstone/agent_v2` and running `uv sync`, the `agent` command is available.

```powershell
agent --help
agent missions list
agent run --help
```

Common flows:

```powershell
# List installed tools and their info
agent tools list

# Show available missions/templates
agent missions list

# Execute a mission (adjust to your templates)
agent run mission project-scaffolding

# Inspect and manage providers
agent providers list
agent providers test openai
```

### Run the minimal debug entrypoint

`agent.py` includes a small debug program that runs the agent end-to-end for a simple mission.

From the repository root (after activating the venv in `capstone/agent_v2`):

```powershell
uv run python .\capstone\agent_v2\agent.py
```


## Development

### Run tests

There are two test locations: the CLI tests under `capstone/agent_v2/cli/tests` and core/unit tests under the repository `tests/` folder.

From `capstone/agent_v2` (with venv active):

```powershell
# CLI tests
uv run -m pytest .\cli\tests -q

# Core/unit tests in the repo root
.\.venv\Scripts\python.exe -m pytest ..\..\tests -q
```

### Linting/formatting

This repo keeps dependencies minimal and focuses on value-first functionality. Use your editor’s formatting and standard linters as needed.


## Configuration Notes

- The agent relies on a TodoList planning flow and emits structured events during execution (thought, action, tool events, asks, completion).
- Git and GitHub tools expect a Windows-friendly `repo_path`. Remotes should be constructed from the GitHub `repo_full_name` when available and gracefully fall back to `remote set-url` if `origin` exists.
- The agent avoids over-engineered validation; provide clear prompts and parameters for best results.


## Working with Assignments

The `assignments/` directory includes datasets, notebooks, and small examples. You can open the notebooks (e.g., `assignments/assignment3/notebooks/data_prep_heart.ipynb`) in your preferred environment. These are independent from the agent’s runtime; they serve as realistic artifacts and inputs for missions.


## Troubleshooting

- Ensure your venv is active: `Get-Command python` should resolve inside `.venv`.
- If `agent` is not found, re-run `uv sync` inside `capstone/agent_v2` and re-activate the venv.
- For LLM calls, verify `OPENAI_API_KEY` is set for the current PowerShell session.
- On Git operations, confirm you have a valid Git installation in PATH and (optionally) `GITHUB_TOKEN` if API calls are required.


## License

This repository is for educational and experimental purposes. Add your preferred license if distributing.