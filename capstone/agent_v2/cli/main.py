"""
Main CLI entry point for the Agent V2 platform.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.traceback import install

from .commands.run import app as run_app
from .commands.missions import app as missions_app
from .commands.tools import app as tools_app
from .commands.providers import app as providers_app
from .commands.sessions import app as sessions_app
from .commands.config import app as config_app
from .commands.dev import app as dev_app
from .plugin_manager import PluginManager
from .config.settings import CLISettings

# Install rich tracebacks
install()

# Initialize console
console = Console()

# Main CLI app
app = typer.Typer(
    name="agent",
    help="Agent V2 Platform CLI - A modern interface for AI-powered task automation",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Developer CLI app (separate entry point for debug features)
dev_cli = typer.Typer(
    name="agent-dev",
    help="Agent V2 Developer CLI - Debug and development tools",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    rich_markup_mode="rich",
)

def initialize_cli():
    """Initialize CLI with plugins and settings."""
    # Load settings
    settings = CLISettings()

    # Initialize plugin manager
    plugin_manager = PluginManager()
    plugin_manager.discover_plugins()
    plugin_manager.setup_plugins(app)

    # Add core command groups
    app.add_typer(run_app, name="run", help="Execute missions and tasks")
    app.add_typer(missions_app, name="missions", help="Manage mission templates")
    app.add_typer(tools_app, name="tools", help="Manage tools and capabilities")
    app.add_typer(providers_app, name="providers", help="Manage LLM providers")
    app.add_typer(sessions_app, name="sessions", help="Manage execution sessions")
    app.add_typer(config_app, name="config", help="Manage configuration")
    app.add_typer(dev_app, name="dev", help="Developer and debug tools")

    # Add dev commands to dev CLI
    dev_cli.add_typer(dev_app, name="", help="Developer tools")

@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version information"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Agent V2 Platform CLI - Modern interface for AI-powered automation.

    Use --help with any command to get detailed information and examples.
    """
    if version:
        from . import __version__
        console.print(f"Agent CLI version {__version__}")
        raise typer.Exit()

    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
        ctx.meta["verbose"] = True

@dev_cli.callback()
def dev_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """Developer tools for Agent V2 platform."""
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
        ctx.meta["verbose"] = True

def cli_main():
    """Main CLI entry point."""
    try:
        initialize_cli()
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if "--verbose" in sys.argv:
            console.print_exception()
        else:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]Use --verbose for detailed error information[/dim]")
        sys.exit(1)

def dev_main():
    """Developer CLI entry point."""
    try:
        initialize_cli()
        dev_cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if "--verbose" in sys.argv:
            console.print_exception()
        else:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]Use --verbose for detailed error information[/dim]")
        sys.exit(1)

if __name__ == "__main__":
    cli_main()