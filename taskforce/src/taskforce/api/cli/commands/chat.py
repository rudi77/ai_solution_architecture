"""Chat command - Interactive chat mode with agent."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from taskforce.application.factory import AgentFactory

app = typer.Typer(help="Interactive chat mode")
console = Console()


@app.command()
def chat(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Configuration profile (overrides global --profile)"
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
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", help="Enable verbose output (overrides global --verbose)"
    ),
):
    """Start interactive chat session with agent.

    For RAG agents, use --user-id, --org-id, and --scope to set user context.

    Examples:
        # Standard chat
        taskforce --profile dev chat

        # RAG chat with user context
        taskforce --profile rag_dev chat --user-id ms-user --org-id MS-corp
    """
    # Get global options from context, allow local override
    global_opts = ctx.obj or {}
    profile = profile or global_opts.get("profile", "dev")
    verbose = verbose if verbose is not None else global_opts.get("verbose", False)
    
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

    async def run_chat_loop():
        # Create agent once for the entire chat session
        factory = AgentFactory()
        
        # If user context provided, create RAG agent with context
        agent = None
        if user_id or org_id or scope:
            user_context = {}
            if user_id:
                user_context["user_id"] = user_id
            if org_id:
                user_context["org_id"] = org_id
            if scope:
                user_context["scope"] = scope

            try:
                agent = await factory.create_rag_agent(
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
        
        if not agent:
            agent = await factory.create_agent(profile=profile)
            console.print("[dim]Agent initialized[/dim]\n")

        session_id = None

        while True:
            # Get user input (blocking, but that's okay in CLI)
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
                # Generate session ID on first message
                if not session_id:
                    import uuid
                    session_id = str(uuid.uuid4())

                # Execute with the same agent instance
                result = await agent.execute(mission=user_input, session_id=session_id)

                # Display result message
                console.print(result.final_message)

                # If there's a pending question, show it prominently
                if result.status == "paused" and result.pending_question:
                    question = result.pending_question.get("question", "")
                    if question and question != result.final_message:
                        console.print(f"[yellow]Question: {question}[/yellow]")

                if verbose:
                    console.print(f"[dim]Session: {session_id}[/dim]")

            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                if verbose:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")

    # Run the async loop
    asyncio.run(run_chat_loop())
