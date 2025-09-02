# IDP Pack (Examples)

This example pack composes the generic `ProductionReActAgent` with an IDP/Git mission prompt and explicit tools.

## Files
- `system_prompt_idp.txt`: IDP copilot mission prompt (Todo List terminology)
- `system_prompt_git.txt`: Minimal Git workflow prompt
- `idp_tools.py`: Re-exports the built-in IDP tool specs
- `run_idp_cli.py`: Simple CLI runner

## Prerequisites
- Python 3.10+
- `OPENAI_API_KEY` set in your environment
- Optional for Git remote creation: `GITHUB_TOKEN`, and optionally `GITHUB_ORG` or `GITHUB_OWNER`

## Quick start (Windows PowerShell)
1) Set environment variables
```powershell
$env:OPENAI_API_KEY = "sk-..."
# Optional for GitHub integration
# $env:GITHUB_TOKEN = "ghp_..."
# $env:GITHUB_ORG = "your-org"    # or set GITHUB_OWNER for user repos
```

2) Run the example CLI (from repo root)
```powershell
python -m capstone.examples.idp_pack.run_idp_cli
```

## Using uv (recommended)
If you use uv for running:
```powershell
uv run python -m capstone.examples.idp_pack.run_idp_cli
```

## Notes
- The core agent is generic; prompts and tools are composed here for the example.
- The agent maintains a persistent Todo List and updates it after each tool run.
