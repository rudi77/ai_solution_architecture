"""RAG chat command for interactive knowledge retrieval."""

import asyncio
import os
import time
import typer
from rich.console import Console
from capstone.agent_v2.agent_factory import create_rag_agent

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
    scope: str = typer.Option("shared", help="Content scope"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent thoughts and actions"),
    show_todos: bool = typer.Option(False, "--show-todos", "-t", help="Display todo list updates in real-time"),
    show_state: bool = typer.Option(False, "--show-state", "-s", help="Display state updates"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode (all events)")
):
    """Start interactive RAG chat session with semantic search.

    Examples:
        # Basic usage
        agent rag chat

        # With verbose output
        agent rag chat --verbose

        # Show todo list updates
        agent rag chat --show-todos

        # Full debug mode
        agent rag chat --debug
    """

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
            agent = create_rag_agent(
                session_id=session_id,
                user_context=user_context
            )
        except Exception as e:
            console.print(f"[red]❌ Failed to create RAG agent: {e}[/red]")
            raise typer.Exit(code=1)

        console.print("[green]✅ RAG Agent started. Type 'exit' to quit.[/green]")
        console.print(f"[dim]📋 User context: {user_context}[/dim]")
        if debug:
            console.print("[yellow]🐛 Debug mode: All events will be displayed[/yellow]")
        elif verbose:
            console.print("[dim]💬 Verbose mode: Showing detailed thoughts and actions[/dim]")
        if show_todos:
            console.print("[dim]📝 Todo tracking: Enabled[/dim]")
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
                            if debug:
                                console.print(f"[dim]ℹ️  Unknown event: {event}[/dim]")
                            continue

                        event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
                        event_data = event.data

                        # === THOUGHT EVENT ===
                        if event_type == "thought":
                            if isinstance(event_data.get('thought'), dict):
                                thought = event_data['thought']
                                step_num = event_data.get('step', '?')
                                rationale = thought.get('rationale', '')
                                action = thought.get('action', {})
                                action_type = action.get('type')
                                tool_name = action.get('tool', '') if isinstance(action, dict) else ''
                                expected = thought.get('expected_outcome', '')
                                confidence = thought.get('confidence', 0)

                                # Always show step number and rationale (basic mode)
                                console.print(f"\n[blue]🤔 Step {step_num}:[/blue] {rationale}")

                                # Verbose: show action details
                                if verbose or debug:
                                    if tool_name:
                                        console.print(f"[dim]   → Action: Call {tool_name}[/dim]")
                                        if debug:
                                            tool_input = action.get('tool_input', {})
                                            console.print(f"[dim]   → Input: {tool_input}[/dim]")
                                    elif action_type:
                                        console.print(f"[dim]   → Action: {action_type}[/dim]")

                                    if expected:
                                        console.print(f"[dim]   → Expected: {expected}[/dim]")
                                    if confidence and debug:
                                        console.print(f"[dim]   → Confidence: {confidence}[/dim]")

                        # === TOOL RESULT EVENT ===
                        elif event_type == "tool_result":
                            success = event_data.get('success', False)
                            status = "✓" if success else "✗"
                            
                            # Check if this is llm_generate result with generated_text
                            if 'generated_text' in event_data:
                                generated_text = event_data.get('generated_text', '')
                                console.print(f"\n[green]✅ Agent Response:[/green]\n{generated_text}")
                            else:
                                # Support both 'results' (SemanticSearchTool) and 'documents' (ListDocumentsTool)
                                results = event_data.get('results') or event_data.get('documents', [])
                                # Also check for explicit 'count' field (ListDocumentsTool provides this)
                                count = event_data.get('count') or (len(results) if isinstance(results, list) else 0)
                                
                                # Basic mode: just show count
                                result_type = "documents" if 'documents' in event_data else "results"
                                console.print(f"[magenta]📊 Result:[/magenta] {status} Found {count} {result_type}")
                                
                                # Verbose: show result previews
                                if verbose and results and count > 0:
                                    first = results[0]
                                    # Handle both document listings and search results
                                    if 'document_title' in first:
                                        # Document listing: show multiple documents
                                        items_to_show = min(5, len(results))
                                        for i, doc in enumerate(results[:items_to_show], 1):
                                            title = doc.get('document_title', 'Unknown')
                                            doc_type = doc.get('document_type', 'N/A')
                                            chunk_count = doc.get('chunk_count', 0)
                                            console.print(f"[dim]   {i}. {title} ({doc_type}, {chunk_count} chunks)[/dim]")
                                        if count > items_to_show:
                                            console.print(f"[dim]   ... and {count - items_to_show} more[/dim]")
                                    else:
                                        # Search result: show first preview only
                                        content = first.get('content_text', '')[:100]
                                        source = first.get('text_document_id', 'unknown')
                                        console.print(f"[dim]   → Preview: {content}... (from {source})[/dim]")

                                # Debug: show all result IDs
                                if debug and results:
                                    if results and 'document_id' in results[0]:
                                        # Document IDs
                                        ids = [r.get('document_id', '?')[:30] for r in results[:5]]
                                    else:
                                        # Content IDs
                                        ids = [r.get('content_id', '?')[:20] for r in results[:5]]
                                    console.print(f"[dim]   → IDs: {', '.join(ids)}...[/dim]")

                        # === STATE UPDATED EVENT (TodoList changes) ===
                        elif event_type == "state_updated":
                            if event_data.get('todolist_created'):
                                if show_todos:
                                    console.print(f"\n[yellow]📝 Todo List Created ({event_data.get('items', 0)} items):[/yellow]")
                                    console.print(event_data.get('todolist', ''))
                                elif verbose or debug:
                                    console.print(f"[yellow]📝 Todo list created with {event_data.get('items', 0)} items[/yellow]")

                            elif event_data.get('step_completed'):
                                step_num = event_data['step_completed']
                                description = event_data.get('description', '')
                                if show_todos:
                                    console.print(f"[green]✓ Step {step_num} completed:[/green] {description}")
                                elif verbose or debug:
                                    console.print(f"[green]✓ Step {step_num} done[/green]")

                            elif event_data.get('step_failed'):
                                step_num = event_data['step_failed']
                                reason = event_data.get('reason') or event_data.get('error', 'unknown')
                                if show_todos or verbose:
                                    console.print(f"[red]✗ Step {step_num} failed:[/red] {reason}")

                            elif event_data.get('plan_updated'):
                                if show_todos or debug:
                                    console.print(f"[yellow]📝 Todo list updated[/yellow]")

                            elif debug:
                                console.print(f"[dim]📌 State updated: {event_data}[/dim]")

                        # === ASK USER EVENT ===
                        elif event_type == "ask_user":
                            console.print(f"\n[yellow]❓ Question:[/yellow] {event_data.get('message', event_data)}")

                        # === COMPLETE EVENT ===
                        elif event_type == "complete":
                            # Check for final answer/summary
                            message = event_data.get('message') or event_data.get('summary')
                            todolist = event_data.get('todolist', '')

                            if message:
                                # Final answer from ActionType.DONE
                                console.print(f"\n[green]✅ Agent:[/green]\n{message}")
                            elif todolist and isinstance(todolist, str) and show_todos:
                                # Show final todolist if requested
                                console.print(f"\n[green]✅ Task completed![/green]")
                                console.print("\n[dim]Final Todo List:[/dim]")
                                console.print(todolist)
                            else:
                                console.print(f"\n[green]✅ Task completed![/green]")

                        # === ERROR EVENT ===
                        elif event_type == "error":
                            console.print(f"[red]❌ Error:[/red] {event_data.get('message', event_data)}")

                        # === TOOL STARTED ===
                        elif event_type == "tool_started":
                            if verbose or debug:
                                tool = event_data.get('tool', 'unknown')
                                console.print(f"[cyan]🔧 Executing:[/cyan] {tool}")

                        # === OTHER EVENTS ===
                        else:
                            if debug:
                                console.print(f"[dim]ℹ️  {event_type}: {event_data}[/dim]")

                    except Exception as e:
                        if debug:
                            console.print(f"[red][Event parsing error: {e}][/red]")
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
