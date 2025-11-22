"""Chat command - Interactive chat mode with agent."""

import asyncio

import typer
from rich.console import Console
from rich.prompt import Prompt

from taskforce.application.executor import AgentExecutor

app = typer.Typer(help="Interactive chat mode")
console = Console()


@app.command()
def chat(profile: str = typer.Option("dev", "--profile", "-p", help="Configuration profile")):
    """Start interactive chat session with agent."""
    console.print("[bold blue]Taskforce Interactive Chat[/bold blue]")
    console.print("[dim]Type 'exit' or 'quit' to end session[/dim]\n")

    executor = AgentExecutor()
    session_id = None

    while True:
        # Get user input
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        # Check for exit commands
        if user_input.lower() in ["exit", "quit", "bye"]:
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        # Execute mission
        console.print("[bold cyan]Agent[/bold cyan]: ", end="")

        try:
            result = asyncio.run(
                executor.execute_mission(
                    mission=user_input, profile=profile, session_id=session_id
                )
            )

            # Store session ID for continuity
            if not session_id:
                session_id = result.session_id

            console.print(result.final_message)

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

