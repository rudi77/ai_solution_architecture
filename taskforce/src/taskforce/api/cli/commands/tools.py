"""Tools command - List and inspect available tools."""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from taskforce.application.factory import AgentFactory

app = typer.Typer(help="Tool management")
console = Console()


@app.command("list")
def list_tools(profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")):
    """List available tools."""
    factory = AgentFactory()
    agent = asyncio.run(factory.create_agent(profile=profile))

    table = Table(title="Available Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")

    # agent.tools is a dict, iterate over values
    for tool in agent.tools.values():
        table.add_row(tool.name, tool.description)

    console.print(table)


@app.command("inspect")
def inspect_tool(
    tool_name: str = typer.Argument(..., help="Tool name to inspect"),
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile"),
):
    """Inspect tool details and parameters."""
    factory = AgentFactory()
    agent = asyncio.run(factory.create_agent(profile=profile))

    # agent.tools is a dict, access by key
    tool = agent.tools.get(tool_name)

    if not tool:
        console.print(f"[red]Tool '{tool_name}' not found[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]{tool.name}[/bold cyan]")
    console.print(f"{tool.description}\n")

    console.print("[bold]Parameters:[/bold]")
    console.print_json(data=tool.parameters_schema)

