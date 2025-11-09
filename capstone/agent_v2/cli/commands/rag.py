"""RAG chat command for interactive knowledge retrieval."""

import asyncio
import os
import time
import typer
from rich.console import Console
from capstone.agent_v2.agent import Agent

console = Console()
app = typer.Typer(help="RAG Knowledge Retrieval Commands")


def validate_azure_config():
    """Validate required Azure Search environment variables."""
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")

    if not endpoint or not api_key:
        console.print("[red]❌ Azure Search not configured. Please set:[/red]")
        console.print("  export AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net")
        console.print("  export AZURE_SEARCH_API_KEY=your-key")
        return False

    return True


@app.command("chat")
def rag_chat(
    user_id: str = typer.Option("test_user", help="User ID for security filtering"),
    org_id: str = typer.Option("test_org", help="Organization ID"),
    scope: str = typer.Option("shared", help="Content scope")
):
    """Start interactive RAG chat session with semantic search."""

    # Validate Azure configuration
    if not validate_azure_config():
        raise typer.Exit(code=1)

    async def run_chat():
        session_id = f"rag_test_{int(time.time())}"
        user_context = {
            "user_id": user_id,
            "org_id": org_id,
            "scope": scope
        }

        console.print("[cyan]🚀 Initializing RAG Agent...[/cyan]")

        try:
            agent = Agent.create_rag_agent(
                session_id=session_id,
                user_context=user_context
            )
        except Exception as e:
            console.print(f"[red]❌ Failed to create RAG agent: {e}[/red]")
            raise typer.Exit(code=1)

        console.print("[green]✅ RAG Agent started. Type 'exit' to quit.[/green]")
        console.print(f"[dim]📋 User context: {user_context}[/dim]")
        console.print("-" * 60)

        while True:
            try:
                query = typer.prompt("\n💬 You")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]👋 Exiting...[/yellow]")
                break

            if query.lower() in ['exit', 'quit', 'q']:
                console.print("[yellow]👋 Goodbye![/yellow]")
                break

            try:
                async for event in agent.execute(query, session_id):
                    try:
                        # AgentEvent has .type (AgentEventType enum) and .data (dict)
                        if not hasattr(event, 'type') or not hasattr(event, 'data'):
                            console.print(f"[dim]ℹ️  Unknown event: {event}[/dim]")
                            continue

                        event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
                        event_data = event.data

                        # Extract thought details if present
                        if event_type == "thought" and isinstance(event_data.get('thought'), dict):
                            thought = event_data['thought']
                            rationale = thought.get('rationale', '')
                            action = thought.get('action', {})
                            tool_name = action.get('tool', '') if isinstance(action, dict) else ''

                            console.print(f"[blue]🤔 Step {event_data.get('step', '?')}:[/blue] {rationale}")
                            if tool_name:
                                console.print(f"[dim]   → Calling: {tool_name}[/dim]")

                        elif event_type == "action":
                            console.print(f"[cyan]🔧 Action:[/cyan] {event_data.get('tool', '')} - {event_data.get('input', '')}")

                        elif event_type == "tool_result":
                            # Show success/failure and truncate results
                            success = event_data.get('success', False)
                            results = event_data.get('results', [])
                            status = "✓" if success else "✗"
                            count = len(results) if isinstance(results, list) else 0
                            console.print(f"[magenta]📊 Result:[/magenta] {status} Found {count} results")

                        elif event_type == "ask_user":
                            console.print(f"[yellow]❓ Question:[/yellow] {event_data.get('message', event_data)}")

                        elif event_type == "complete":
                            # Extract final answer from todolist if present
                            todolist = event_data.get('todolist', '')
                            if todolist and isinstance(todolist, str):
                                # Skip the todolist dump, agent finished
                                console.print(f"\n[green]✅ Task completed![/green]")
                            else:
                                console.print(f"\n[green]✅ Agent:[/green] {event_data.get('message', event_data)}")

                        elif event_type == "error":
                            console.print(f"[red]❌ Error:[/red] {event_data.get('message', event_data)}")

                        else:
                            # Skip verbose state updates
                            if event_type not in ["state_updated", "tool_started"]:
                                console.print(f"[dim]ℹ️  {event_type}[/dim]")

                    except Exception as e:
                        # Silently skip malformed events
                        console.print(f"[dim][Event parsing error: {e}][/dim]")
                        continue

            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Query interrupted. Type 'exit' to quit.[/yellow]")
                continue
            except Exception as e:
                console.print(f"[red]❌ Error during query execution: {e}[/red]")
                console.print("[dim]You can try another query or type 'exit' to quit.[/dim]")

    try:
        asyncio.run(run_chat())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Exiting...[/yellow]")
