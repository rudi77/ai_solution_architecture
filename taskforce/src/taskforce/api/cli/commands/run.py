"""Run command - Execute agent missions."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from taskforce.application.executor import AgentExecutor

app = typer.Typer(help="Execute agent missions")
console = Console()


@app.command("mission")
def run_mission(
    mission: str = typer.Argument(..., help="Mission description"),
    profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile"),
    session_id: Optional[str] = typer.Option(
        None, "--session", "-s", help="Resume existing session"
    ),
):
    """Execute an agent mission."""
    console.print(f"[bold blue]Starting mission:[/bold blue] {mission}")
    console.print(f"[dim]Profile: {profile}[/dim]\n")

    executor = AgentExecutor()

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Executing mission...", total=None)

        def progress_callback(update):
            progress.update(task, description=update.message)

        # Execute mission with progress tracking
        result = asyncio.run(
            executor.execute_mission(
                mission=mission,
                profile=profile,
                session_id=session_id,
                progress_callback=progress_callback,
            )
        )

    # Display results
    if result.status == "completed":
        console.print(f"\n[bold green]✓ Mission completed![/bold green]")
        console.print(f"Session ID: {result.session_id}")
        console.print(f"\n{result.final_message}")
    else:
        console.print(f"\n[bold red]✗ Mission failed[/bold red]")
        console.print(f"Session ID: {result.session_id}")
        console.print(f"\n{result.final_message}")

