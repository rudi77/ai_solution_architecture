"""Taskforce CLI entry point."""

import typer
from rich.console import Console

from taskforce.api.cli.commands import chat, config, missions, run, sessions, tools

app = typer.Typer(
    name="taskforce",
    help="Taskforce - Production-ready ReAct agent framework",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Register command groups
app.add_typer(run.app, name="run", help="Execute missions")
app.add_typer(chat.app, name="chat", help="Interactive chat mode")
app.add_typer(tools.app, name="tools", help="Tool management")
app.add_typer(sessions.app, name="sessions", help="Session management")
app.add_typer(missions.app, name="missions", help="Mission management")
app.add_typer(config.app, name="config", help="Configuration management")


@app.callback()
def main(
    ctx: typer.Context,
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Taskforce Agent CLI."""
    # Store global options in context for subcommands
    ctx.obj = {"profile": profile, "verbose": verbose}


@app.command()
def version():
    """Show Taskforce version."""
    from taskforce import __version__

    console.print(f"[bold blue]Taskforce[/bold blue] version [cyan]{__version__}[/cyan]")


if __name__ == "__main__":
    app()
