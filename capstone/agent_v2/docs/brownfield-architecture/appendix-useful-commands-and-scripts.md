# Appendix - Useful Commands and Scripts

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
