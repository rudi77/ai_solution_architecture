"""Run command - Execute agent missions."""

import asyncio
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from taskforce.api.cli.output_formatter import TaskforceConsole
from taskforce.application.executor import AgentExecutor

app = typer.Typer(help="Execute agent missions")


@app.command("mission")
def run_mission(
    ctx: typer.Context,
    mission: str = typer.Argument(..., help="Mission description"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Configuration profile (overrides global --profile)"),
    session_id: Optional[str] = typer.Option(
        None, "--session", "-s", help="Resume existing session"
    ),
    debug: Optional[bool] = typer.Option(
        None, "--debug", help="Enable debug output (overrides global --debug)"
    ),
    lean: bool = typer.Option(
        False, "--lean", "-l", help="Use LeanAgent (native tool calling, PlannerTool)"
    ),
):
    """Execute an agent mission.
    
    Examples:
        # Execute a simple mission
        taskforce run mission "Analyze data.csv"
        
        # Use LeanAgent (new simplified architecture)
        taskforce run mission "Plan and execute" --lean
        
        # Resume a previous session
        taskforce run mission "Continue analysis" --session abc-123
        
        # Debug mode to see agent internals
        taskforce --debug run mission "Debug this task"
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
    
    # Initialize fancy console
    tf_console = TaskforceConsole(debug=debug)
    
    # Print banner
    tf_console.print_banner()
    
    # Show mission info
    tf_console.print_system_message(f"Mission: {mission}", "system")
    if session_id:
        tf_console.print_system_message(f"Resuming session: {session_id}", "info")
    tf_console.print_system_message(f"Profile: {profile}", "info")
    if lean:
        tf_console.print_system_message("Using LeanAgent (native tool calling)", "info")
    tf_console.print_divider()

    executor = AgentExecutor()

    with Progress(
        SpinnerColumn(), 
        TextColumn("[progress.description]{task.description}"), 
        console=tf_console.console
    ) as progress:
        task = progress.add_task("[>] Executing mission...", total=None)

        def progress_callback(update):
            if debug:
                progress.update(task, description=f"[>] {update.message}")
            else:
                progress.update(task, description="[>] Working...")

        # Execute mission with progress tracking
        result = asyncio.run(
            executor.execute_mission(
                mission=mission,
                profile=profile,
                session_id=session_id,
                progress_callback=progress_callback,
                use_lean_agent=lean,
            )
        )

    tf_console.print_divider()
    
    # Display results
    if result.status == "completed":
        tf_console.print_success("Mission completed!")
        tf_console.print_debug(f"Session ID: {result.session_id}")
        tf_console.print_agent_message(result.final_message)
    else:
        tf_console.print_error(f"Mission {result.status}")
        tf_console.print_debug(f"Session ID: {result.session_id}")
        tf_console.print_agent_message(result.final_message)

