"""
Main CLI entry point for the Agent V2 platform.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
import logging

import typer
from rich.console import Console
from rich.traceback import install
import structlog
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fix Windows Unicode support
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

    # Also set environment variables for proper Unicode handling
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from .commands.run import app as run_app
from .commands.chat import app as chat_app
from .commands.missions import app as missions_app
from .commands.tools import app as tools_app
from .commands.providers import app as providers_app
from .commands.sessions import app as sessions_app
from .commands.config import app as config_app
from .commands.dev import app as dev_app
from .commands.rag import app as rag_app
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


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for console or JSON output."""
    level = logging.DEBUG if debug or os.getenv("AGENT_DEBUG") else logging.WARN
    logging.basicConfig(level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if (debug or os.getenv("AGENT_DEBUG")) else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
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
    app.add_typer(chat_app, name="chat", help="Interactive chat with the agent")
    app.add_typer(missions_app, name="missions", help="Manage mission templates")
    app.add_typer(tools_app, name="tools", help="Manage tools and capabilities")
    app.add_typer(providers_app, name="providers", help="Manage LLM providers")
    app.add_typer(sessions_app, name="sessions", help="Manage execution sessions")
    app.add_typer(config_app, name="config", help="Manage configuration")
    app.add_typer(dev_app, name="dev", help="Developer and debug tools")
    app.add_typer(rag_app, name="rag", help="RAG knowledge retrieval commands")

    # Add dev commands to dev CLI
    dev_cli.add_typer(dev_app, name="", help="Developer tools")

@app.command("ask", hidden=True)
def quick_ask(message: str = typer.Argument(help="Message to send to the agent")):
    """Quick way to ask the agent something directly."""
    import asyncio
    from .commands.chat import _quick_chat
    from pathlib import Path
    import uuid

    session_id = f"ask-{uuid.uuid4()}"
    work_dir = Path.cwd() / ".agent_temp"
    asyncio.run(_quick_chat(message, work_dir, session_id))

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
    # Ensure logging is configured as early as possible
    setup_logging(debug=verbose)

@dev_cli.callback()
def dev_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """Developer tools for Agent V2 platform."""
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
        ctx.meta["verbose"] = True
    setup_logging(debug=verbose)

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