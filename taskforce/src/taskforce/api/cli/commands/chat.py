"""Chat command - Interactive chat mode with agent."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from taskforce.application.executor import AgentExecutor
from taskforce.application.factory import AgentFactory

app = typer.Typer(help="Interactive chat mode")
console = Console()


@app.command()
def chat(
    profile: str = typer.Option(
        "dev", "--profile", "-p", help="Configuration profile"
    ),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="User ID for RAG context"
    ),
    org_id: Optional[str] = typer.Option(
        None, "--org-id", help="Organization ID for RAG context"
    ),
    scope: Optional[str] = typer.Option(
        None, "--scope", help="Scope for RAG context (shared/org/user)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Enable verbose output"
    ),
):
    """Start interactive chat session with agent.

    For RAG agents, use --user-id, --org-id, and --scope to set user context.

    Examples:
        # Standard chat
        taskforce chat --profile dev

        # RAG chat with user context
        taskforce chat --profile rag_dev --user-id ms-user --org-id MS-corp
    """
    console.print("[bold blue]Taskforce Interactive Chat[/bold blue]")

    # Display context info if RAG parameters provided
    if user_id or org_id or scope:
        console.print("[dim]RAG Context:[/dim]")
        if user_id:
            console.print(f"[dim]  User ID: {user_id}[/dim]")
        if org_id:
            console.print(f"[dim]  Org ID: {org_id}[/dim]")
        if scope:
            console.print(f"[dim]  Scope: {scope}[/dim]")

    console.print(f"[dim]Profile: {profile}[/dim]")
    console.print("[dim]Type 'exit' or 'quit' to end session[/dim]\n")

    # Create executor with optional user context for RAG
    executor = AgentExecutor()

    # If user context provided, create RAG agent with context
    if user_id or org_id or scope:
        user_context = {}
        if user_id:
            user_context["user_id"] = user_id
        if org_id:
            user_context["org_id"] = org_id
        if scope:
            user_context["scope"] = scope

        # Create factory and RAG agent with user context
        factory = AgentFactory()
        try:
            _ = factory.create_rag_agent(
                profile=profile, user_context=user_context
            )
            console.print(
                "[dim]RAG agent initialized with user context[/dim]\n"
            )
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not create RAG agent: {e}[/yellow]"
            )
            console.print("[dim]Falling back to standard agent[/dim]\n")

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

            if verbose:
                console.print(f"[dim]Session: {session_id}[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            if verbose:
                import traceback

                console.print(f"[dim]{traceback.format_exc()}[/dim]")


