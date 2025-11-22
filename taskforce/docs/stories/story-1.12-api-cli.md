# Story 1.12: Implement API Layer - CLI Interface

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.12  
**Status**: Pending  
**Priority**: High  
**Estimated Points**: 4  
**Dependencies**: Story 1.10 (Executor Service)

---

## User Story

As a **developer**,  
I want **a Typer CLI adapted from Agent V2**,  
so that **developers can use Taskforce via command line**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/api/cli/` directory
2. ✅ Adapt structure from `capstone/agent_v2/cli/`:
   - `main.py` - CLI entry point with Typer app
   - `commands/run.py` - Execute missions
   - `commands/chat.py` - Interactive chat mode
   - `commands/tools.py` - List/inspect tools
   - `commands/sessions.py` - Session management
   - `commands/missions.py` - Mission management
   - `commands/config.py` - Configuration commands
3. ✅ All commands use `AgentExecutor` service from application layer
4. ✅ Preserve Rich terminal output (colored status, progress bars, tables)
5. ✅ CLI entry point defined in `pyproject.toml`: `taskforce` command
6. ✅ Support for `--profile` flag to select configuration profile
7. ✅ Integration tests via CliRunner verify all commands

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 CLI (`agent` command) continues to work
- **IV2: Integration Point Verification** - Taskforce CLI (`taskforce` command) produces same outputs as Agent V2 CLI for comparable commands
- **IV3: Performance Impact Verification** - CLI command response time matches Agent V2 (±10%)

---

## Technical Notes

**CLI Entry Point:**

```python
# taskforce/src/taskforce/api/cli/main.py
import typer
from rich.console import Console
from taskforce.api.cli.commands import run, chat, tools, sessions, config

app = typer.Typer(
    name="taskforce",
    help="Taskforce - Production-ready ReAct agent framework",
    add_completion=True
)

console = Console()

# Register command groups
app.add_typer(run.app, name="run", help="Execute missions")
app.add_typer(chat.app, name="chat", help="Interactive chat mode")
app.add_typer(tools.app, name="tools", help="Tool management")
app.add_typer(sessions.app, name="sessions", help="Session management")
app.add_typer(config.app, name="config", help="Configuration management")

@app.callback()
def main(
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Taskforce Agent CLI"""
    # Set global profile
    app.state = {"profile": profile, "verbose": verbose}

if __name__ == "__main__":
    app()
```

**Run Command:**

```python
# taskforce/src/taskforce/api/cli/commands/run.py
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from taskforce.application.executor import AgentExecutor

app = typer.Typer()
console = Console()

@app.command("mission")
def run_mission(
    mission: str = typer.Argument(..., help="Mission description"),
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile"),
    session_id: str = typer.Option(None, "--session", "-s", help="Resume existing session")
):
    """Execute an agent mission."""
    
    console.print(f"[bold blue]Starting mission:[/bold blue] {mission}")
    console.print(f"[dim]Profile: {profile}[/dim]\n")
    
    executor = AgentExecutor()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Executing mission...", total=None)
        
        def progress_callback(update):
            progress.update(task, description=update.message)
        
        # Execute mission with progress tracking
        import asyncio
        result = asyncio.run(executor.execute_mission(
            mission=mission,
            profile=profile,
            session_id=session_id,
            progress_callback=progress_callback
        ))
    
    # Display results
    if result.status == "completed":
        console.print(f"\n[bold green]✓ Mission completed![/bold green]")
        console.print(f"Session ID: {result.session_id}")
        console.print(f"\n{result.final_message}")
    else:
        console.print(f"\n[bold red]✗ Mission failed[/bold red]")
        console.print(f"Session ID: {result.session_id}")
        console.print(f"\n{result.final_message}")
```

**Tools Command:**

```python
# taskforce/src/taskforce/api/cli/commands/tools.py
import typer
from rich.console import Console
from rich.table import Table
from taskforce.application.factory import AgentFactory

app = typer.Typer()
console = Console()

@app.command("list")
def list_tools(
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")
):
    """List available tools."""
    
    factory = AgentFactory()
    agent = factory.create_agent(profile=profile)
    
    table = Table(title="Available Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    
    for tool in agent.tools:
        table.add_row(tool.name, tool.description)
    
    console.print(table)

@app.command("inspect")
def inspect_tool(
    tool_name: str = typer.Argument(..., help="Tool name to inspect"),
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")
):
    """Inspect tool details and parameters."""
    
    factory = AgentFactory()
    agent = factory.create_agent(profile=profile)
    
    tool = agent.tools.get(tool_name)
    if not tool:
        console.print(f"[red]Tool '{tool_name}' not found[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold cyan]{tool.name}[/bold cyan]")
    console.print(f"{tool.description}\n")
    
    console.print("[bold]Parameters:[/bold]")
    console.print_json(data=tool.parameters_schema)
```

**Sessions Command:**

```python
# taskforce/src/taskforce/api/cli/commands/sessions.py
import typer
from rich.console import Console
from rich.table import Table
from taskforce.application.factory import AgentFactory

app = typer.Typer()
console = Console()

@app.command("list")
def list_sessions(
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")
):
    """List all agent sessions."""
    
    factory = AgentFactory()
    agent = factory.create_agent(profile=profile)
    
    import asyncio
    sessions = asyncio.run(agent.state_manager.list_sessions())
    
    table = Table(title="Agent Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Status", style="white")
    
    for session_id in sessions:
        state = asyncio.run(agent.state_manager.load_state(session_id))
        status = state.get("status", "unknown") if state else "unknown"
        table.add_row(session_id, status)
    
    console.print(table)

@app.command("show")
def show_session(
    session_id: str = typer.Argument(..., help="Session ID"),
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")
):
    """Show session details."""
    
    factory = AgentFactory()
    agent = factory.create_agent(profile=profile)
    
    import asyncio
    state = asyncio.run(agent.state_manager.load_state(session_id))
    
    if not state:
        console.print(f"[red]Session '{session_id}' not found[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Session:[/bold] {session_id}")
    console.print(f"[bold]Mission:[/bold] {state.get('mission', 'N/A')}")
    console.print(f"[bold]Status:[/bold] {state.get('status', 'N/A')}")
    console.print_json(data=state)
```

**pyproject.toml Entry Point:**

```toml
[project.scripts]
taskforce = "taskforce.api.cli.main:app"
```

---

## Testing Strategy

```python
# tests/integration/test_cli_commands.py
from typer.testing import CliRunner
from taskforce.api.cli.main import app

runner = CliRunner()

def test_run_mission_command():
    result = runner.invoke(app, ["run", "mission", "Create a hello world function"])
    
    assert result.exit_code == 0
    assert "Starting mission" in result.output
    assert "Session ID" in result.output

def test_tools_list_command():
    result = runner.invoke(app, ["tools", "list"])
    
    assert result.exit_code == 0
    assert "Available Tools" in result.output
    assert "python" in result.output

def test_tools_inspect_command():
    result = runner.invoke(app, ["tools", "inspect", "python"])
    
    assert result.exit_code == 0
    assert "Parameters" in result.output

def test_sessions_list_command():
    result = runner.invoke(app, ["sessions", "list"])
    
    assert result.exit_code == 0
    assert "Agent Sessions" in result.output

def test_profile_flag():
    result = runner.invoke(app, ["--profile", "prod", "tools", "list"])
    
    assert result.exit_code == 0
```

---

## Definition of Done

- [ ] CLI structure created in `api/cli/`
- [ ] All command groups implemented (run, chat, tools, sessions, config)
- [ ] Commands use AgentExecutor service
- [ ] Rich terminal output preserved (colors, progress bars, tables)
- [ ] Entry point defined in pyproject.toml
- [ ] `--profile` flag supported across all commands
- [ ] Integration tests via CliRunner (≥80% coverage)
- [ ] CLI response time matches Agent V2 (±10%)
- [ ] Code review completed
- [ ] Code committed to version control

