"""Chat command - Interactive chat mode with agent."""

import asyncio
from typing import Optional

import typer

from taskforce.api.cli.output_formatter import TaskforceConsole
from taskforce.application.factory import AgentFactory

app = typer.Typer(help="Interactive chat mode")


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
    debug: Optional[bool] = typer.Option(
        None, "--debug", help="Enable debug output (overrides global --debug)"
    ),
):
    """Start interactive chat session with agent.

    For RAG agents, use --user-id, --org-id, and --scope to set user context.

    Examples:
        # Standard chat
        taskforce --profile dev chat

        # RAG chat with user context
        taskforce --profile rag_dev chat --user-id ms-user --org-id MS-corp
        
        # Debug mode to see agent thoughts and actions
        taskforce --debug chat
    """
    # Get global options from context, allow local override
    global_opts = ctx.obj or {}
    profile = profile or global_opts.get("profile", "dev")
    debug = debug if debug is not None else global_opts.get("debug", False)
    
    # Configure logging level based on debug flag
    import structlog
    import logging
    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        )
    else:
        logging.basicConfig(level=logging.WARNING, format="%(message)s")
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        )
    
    # Initialize our fancy console
    tf_console = TaskforceConsole(debug=debug)
    
    # Print banner
    tf_console.print_banner()
    
    # Build user context if provided
    user_context = None
    if user_id or org_id or scope:
        user_context = {}
        if user_id:
            user_context["user_id"] = user_id
        if org_id:
            user_context["org_id"] = org_id
        if scope:
            user_context["scope"] = scope

    # Show session info
    import uuid
    session_id = str(uuid.uuid4())
    tf_console.print_session_info(session_id, profile, user_context)
    
    tf_console.print_system_message("Type 'exit', 'quit', or press Ctrl+C to end session", "info")
    tf_console.print_divider()

    async def run_chat_loop():
        # Create agent once for the entire chat session
        factory = AgentFactory()
        
        # If user context provided, create RAG agent with context
        agent = None
        if user_context:
            try:
                agent = await factory.create_rag_agent(
                    profile=profile, user_context=user_context
                )
                tf_console.print_system_message(
                    "RAG agent initialized with user context", "success"
                )
                tf_console.print_divider()
            except Exception as e:
                tf_console.print_warning(
                    f"Could not create RAG agent: {e}. Falling back to standard agent."
                )
        
        if not agent:
            agent = await factory.create_agent(profile=profile)
            tf_console.print_system_message("Agent initialized", "success")
            tf_console.print_divider()

        try:
            while True:
                # Get user input (blocking, but that's okay in CLI)
                try:
                    user_input = tf_console.prompt()
                except (KeyboardInterrupt, EOFError):
                    tf_console.print_divider()
                    tf_console.print_system_message("Goodbye! 👋", "info")
                    break

                # Check for exit commands
                if user_input.lower() in ["exit", "quit", "bye"]:
                    tf_console.print_divider()
                    tf_console.print_system_message("Goodbye! 👋", "info")
                    break

                if not user_input.strip():
                    continue

                # Show user message in panel
                tf_console.print_user_message(user_input)

                try:
                    # === CONVERSATION HISTORY MANAGEMENT ===
                    # Load current state and update conversation history with user message
                    state = await agent.state_manager.load_state(session_id) or {}
                    history = state.get("conversation_history", [])
                    
                    # Append user message to history
                    history.append({"role": "user", "content": user_input})
                    state["conversation_history"] = history
                    
                    # Save state so agent can access the updated history
                    await agent.state_manager.save_state(session_id, state)
                    
                    # Execute with the same agent instance
                    result = await agent.execute(mission=user_input, session_id=session_id)
                    
                    # Reload state (agent may have modified it) and append agent response
                    state = await agent.state_manager.load_state(session_id) or {}
                    history = state.get("conversation_history", [])
                    history.append({"role": "assistant", "content": result.final_message})
                    state["conversation_history"] = history
                    await agent.state_manager.save_state(session_id, state)
                    # === END CONVERSATION HISTORY MANAGEMENT ===

                    # Extract thought if available (for debug mode)
                    thought = None
                    if debug and hasattr(result, 'thoughts') and result.thoughts:
                        thought = result.thoughts[-1] if result.thoughts else None

                    # Display agent response
                    tf_console.print_agent_message(result.final_message, thought=thought)

                    # If there's a pending question, show it prominently
                    if result.status == "paused" and result.pending_question:
                        question = result.pending_question.get("question", "")
                        if question and question != result.final_message:
                            tf_console.print_warning(f"Question: {question}")

                    # Debug info
                    tf_console.print_debug(f"Status: {result.status}")

                except Exception as e:
                    tf_console.print_error(f"Execution failed: {str(e)}", exception=e if debug else None)
        finally:
            # Clean up MCP connections to avoid cancel scope errors
            if agent:
                await agent.close()

    # Run the async loop
    asyncio.run(run_chat_loop())
