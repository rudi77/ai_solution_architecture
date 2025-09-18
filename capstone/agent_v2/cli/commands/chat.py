"""
Chat command for interactive conversation with the agent.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner

from ..config.settings import CLISettings

console = Console()
app = typer.Typer(help="Interactive chat with the agent")


@app.command()
def start(
    mission: Optional[str] = typer.Option(
        None,
        "--mission", "-m",
        help="Initial mission for the agent"
    ),
    mission_file: Optional[Path] = typer.Option(
        None,
        "--mission-file", "-mf",
        help="Path to a file containing the initial mission",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    work_dir: Optional[Path] = typer.Option(
        None,
        "--work-dir", "-w",
        help="Working directory for the agent"
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider", "-p",
        help="LLM provider to use"
    ),
    session_name: Optional[str] = typer.Option(
        None,
        "--session", "-s",
        help="Session name (auto-generated if not provided)"
    ),
):
    """
    Start an interactive chat session with the agent.

    Examples:
        agent chat start
        agent chat start --mission "Help me organize my files"
        agent chat start --mission-file ./path/to/mission.md
        agent chat start --work-dir ./workspace --provider anthropic
    """
    settings = CLISettings()
    selected_provider = provider or settings.default_provider

    # Resolve mission from file if provided (file overrides --mission)
    resolved_mission = mission
    if mission_file is not None:
        try:
            resolved_mission = mission_file.read_text(encoding="utf-8")
            # Inform if both were provided
            if mission is not None:
                console.print("[dim]Note: --mission-file provided; overriding --mission text.[/dim]")
        except Exception as e:
            console.print(f"[red]❌ Failed to read mission file: {e}[/red]")
            raise typer.Exit(code=1)

    # Generate session info
    session_id = session_name or f"chat-{uuid.uuid4()}"
    if not work_dir:
        work_dir = Path.cwd() / ".agent_workspace"

    # Display session info
    console.print(Panel.fit(
        f"[bold blue]Agent Chat Session[/bold blue]\n\n"
        f"[dim]Session ID:[/dim] {session_id[:16]}...\n"
        f"[dim]Provider:[/dim] {selected_provider}\n"
        f"[dim]Work Directory:[/dim] {work_dir}\n"
        f"[dim]Mission:[/dim] {('from file: ' + str(mission_file)) if (mission_file is not None) else (resolved_mission or 'None - free chat')}\n\n"
        f"[yellow]Type 'exit' to end the session[/yellow]",
        title="🤖 Agent V2 Chat"
    ))

    # Start the chat loop
    asyncio.run(_demo_chat_loop(resolved_mission, work_dir, selected_provider, session_id))


@app.command()
def resume(
    session_id: str = typer.Argument(help="Session ID to resume"),
):
    """
    Resume a previous chat session.

    Examples:
        agent chat resume sess-abc123
    """
    console.print(f"[blue]Resuming chat session: {session_id}[/blue]")

    # TODO: Load session state and resume
    console.print("[yellow]Session resumption not yet implemented[/yellow]")
    console.print("This would load the previous conversation and agent state")


async def _demo_chat_loop(mission: Optional[str], work_dir: Path, provider: str, session_id: str):
    """Real agent chat loop implementation."""
    import os

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]❌ Error: Please set OPENAI_API_KEY environment variable before running.[/red]")
        console.print("[dim]You can set it with: export OPENAI_API_KEY='your-api-key'[/dim]")
        return

    try:
        # Import the real agent
        import sys
        from pathlib import Path as PathLib

        # Add the correct directories to sys.path for capstone imports
        current_file = PathLib(__file__)
        root_dir = current_file.parent.parent.parent.parent.parent  # Same path calculation

        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))

        from capstone.agent_v2.agent import Agent, AgentEventType, GENERIC_SYSTEM_PROMPT

        console.print("[green]🤖 Initializing real Agent...[/green]")

        # # Initial user message
        # # mission can be an empty string, so we need to check for None
        # if mission is not None and mission != "":
        #     current_input = f"My mission is: {mission}. How can you help me with this?"
        #     console.print(f"[bold green]You[/bold green]: {current_input}")

        # Create the real agent like in your debug script
        agent = Agent.create_agent(
            name="AgentV2-Chat",
            description="Interactive chat agent with full capabilities",
            system_prompt=GENERIC_SYSTEM_PROMPT,
            mission=mission,
            work_dir=str(work_dir.resolve()),
            llm=None,  # Use default LLM configuration
        )

        console.print("[green]✅ Agent initialized successfully![/green]")
        console.print("[dim]You're now chatting with the real Agent V2...[/dim]\n")


        current_input = Prompt.ask("[bold green]You[/bold green]")

        done = False
        while not done:
            if current_input.lower() in ['exit', 'quit', 'bye']:
                console.print("[yellow]Ending chat session. Goodbye! 👋[/yellow]")
                break

            console.print(f"\n[dim]Agent processing your message...[/dim]")

            try:
                # Use the real agent execution loop like in your debug script
                with Live(Spinner("dots", text="Agent thinking..."), console=console, refresh_per_second=4) as live:
                    async for ev in agent.execute(user_message=current_input, session_id=session_id):
                        if ev.type.name == AgentEventType.ASK_USER.name:
                            # Clear spinner and show the question
                            live.stop()
                            question = ev.data.get("question", "Agent has a question:")
                            console.print(f"\n[bold blue]🤖 Agent[/bold blue]: {question}")
                            current_input = Prompt.ask("[bold green]You[/bold green]")
                            #break

                        elif ev.type.name == AgentEventType.STATE_UPDATED.name:
                            # Show state updates
                            state_data = ev.data

                            # Show any agent response or reasoning
                            if 'response' in state_data:
                                live.stop()
                                console.print(f"\n[bold blue]🤖 Agent[/bold blue]:")
                                console.print(Panel(
                                    Markdown(state_data['response']),
                                    border_style="blue",
                                    padding=(1, 2)
                                ))

                            # Show todo list updates if available
                            if 'todolist' in state_data and state_data['todolist']:
                                console.print("\n[dim]📋 Agent's current plan:[/dim]")
                                todolist = state_data['todolist']
                                if isinstance(todolist, str):
                                    console.print(f"[dim]{todolist}[/dim]")
                                elif isinstance(todolist, list):
                                    for i, item in enumerate(todolist, 1):
                                        status = "✅" if item.get('completed', False) else "⏳"
                                        console.print(f"[dim]{status} {i}. {item}[/dim]")
                                elif hasattr(todolist, 'items'):
                                    for i, item in enumerate(todolist.items, 1):
                                        status = "✅" if item.status.name == 'COMPLETED' else "⏳"
                                        console.print(f"[dim]{status} {i}. {item.task}[/dim]")

                        elif ev.type.name == AgentEventType.TOOL_STARTED.name:
                            tool_name = ev.data.get('tool', 'Unknown')
                            console.print(f"[dim]🔧 Using tool: {tool_name}[/dim]")

                        elif ev.type.name == AgentEventType.TOOL_RESULT.name:
                            success = ev.data.get('success', False)
                            tool_name = ev.data.get('tool', 'Tool')
                            result = ev.data.get('result', '')
                            if success:
                                console.print(f"[dim]✅ {tool_name} completed[/dim]")
                                if result and len(str(result)) < 200:  # Show short results
                                    console.print(f"[dim]   Result: {result}[/dim]")
                            else:
                                console.print(f"[dim]❌ {tool_name} failed[/dim]")
                                if result:
                                    console.print(f"[dim]   Error: {result}[/dim]")

                        elif ev.type.name == AgentEventType.COMPLETE.name:
                            live.stop()
                            console.print("\n[green]✅ Task completed![/green]")
                            todolist_markdown = ev.data.get("todolist")

                            # print the todolist in a panel
                            console.print(Panel(
                                Markdown(todolist_markdown),
                                border_style="green",
                                padding=(1, 2)
                            ))
                
                            # Show final results
                            current_input = Prompt.ask("\n[bold green]You[/bold green] (or 'exit' to quit)")
                            done = True
                            #break

            except Exception as e:
                console.print(f"\n[red]❌ Agent execution error: {e}[/red]")
                console.print(f"[dim]Error details: {type(e).__name__}[/dim]")
                current_input = Prompt.ask("\n[bold green]You[/bold green] (try again or 'exit' to quit)")

    except ImportError as e:
        console.print(f"[red]❌ Could not import Agent: {e}[/red]")
        console.print("[yellow]Make sure you're in the correct directory and the agent module is available[/yellow]")
        console.print(f"[dim]Current directory: {Path.cwd()}[/dim]")
        console.print(f"[dim]Expected agent.py at: {Path.cwd() / 'agent.py'}[/dim]")
    except Exception as e:
        console.print(f"[red]❌ Chat initialization error: {e}[/red]")


def _generate_demo_response(user_input: str, mission: Optional[str], work_dir: Path) -> str:
    """Generate a demo response based on user input."""
    user_lower = user_input.lower()

    if "hello" in user_lower or "hi" in user_lower:
        return "Hello! I'm your AI assistant. I can help you with various tasks like:\n\n- 📁 File and directory operations\n- 💻 Code generation and review\n- 📊 Data analysis\n- 🔍 Research and information gathering\n\nWhat would you like me to help you with?"

    elif "file" in user_lower and "create" in user_lower:
        filename = "example_file.py"
        return f"I'll create a file for you! Let me create `{filename}` in your working directory.\n\n```python\n# Example Python file\nprint('Hello, World!')\n\ndef main():\n    print('This is a demo file created by the agent')\n\nif __name__ == '__main__':\n    main()\n```\n\nFile created at: `{work_dir}/{filename}`\n\n✅ **Task completed!** The file has been created successfully."

    elif "python" in user_lower and "function" in user_lower:
        return "I'll help you write a Python function! Here's an example:\n\n```python\ndef calculate_fibonacci(n):\n    \"\"\"\n    Calculate the nth Fibonacci number.\n    \n    Args:\n        n (int): The position in the Fibonacci sequence\n        \n    Returns:\n        int: The nth Fibonacci number\n    \"\"\"\n    if n <= 0:\n        return 0\n    elif n == 1:\n        return 1\n    else:\n        return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)\n\n# Example usage\nprint(calculate_fibonacci(10))  # Output: 55\n```\n\nThis function calculates Fibonacci numbers recursively. Would you like me to modify it or create a different function?"

    elif "organize" in user_lower or "clean" in user_lower:
        return "I can help you organize your files! Here's what I can do:\n\n## 📋 **File Organization Plan**\n\n1. **Scan Directory**: Analyze your current file structure\n2. **Categorize Files**: Group files by type (documents, images, code, etc.)\n3. **Create Folders**: Set up organized directory structure\n4. **Move Files**: Relocate files to appropriate folders\n5. **Generate Report**: Summary of changes made\n\nShould I proceed with organizing your files? I'll start by scanning the current directory."

    elif mission and ("mission" in user_lower or "task" in user_lower):
        return f"Great! Your mission is: **{mission}**\n\nHere's how I can help you accomplish this:\n\n## 🎯 **Action Plan**\n\n1. **Break down the mission** into smaller, manageable tasks\n2. **Identify required tools** and resources\n3. **Execute step by step** with regular progress updates\n4. **Provide detailed feedback** on each completed step\n\nLet me start by analyzing what needs to be done for your specific mission. What specific aspect would you like me to focus on first?"

    else:
        return f"I understand you're asking about: **{user_input}**\n\nI'm currently in demo mode, but in the full version I would:\n\n- 🧠 **Analyze your request** using advanced AI reasoning\n- 🛠️ **Use appropriate tools** to complete the task\n- 💬 **Ask clarifying questions** if needed\n- 📋 **Break down complex tasks** into steps\n- ✅ **Provide detailed results** with explanations\n\nThe real agent integration is coming soon! For now, I can demonstrate the chat interface and show you what the full experience will be like.\n\nWhat else would you like to explore?"


@app.command("list")
def list_sessions():
    """
    List previous chat sessions.

    Examples:
        agent chat list
    """
    console.print("[blue]Previous Chat Sessions:[/blue]")

    # TODO: Implement session listing from storage
    sessions = [
        {"id": "chat-abc123", "started": "2025-01-18 10:30", "mission": "File organization"},
        {"id": "chat-def456", "started": "2025-01-18 11:15", "mission": "Code review"},
        {"id": "chat-ghi789", "started": "2025-01-18 14:20", "mission": "None"},
    ]

    from rich.table import Table
    table = Table()
    table.add_column("Session ID", style="cyan")
    table.add_column("Started", style="green")
    table.add_column("Mission", style="white")

    for session in sessions:
        table.add_row(
            session["id"][:12] + "...",
            session["started"],
            session["mission"] or "[dim]Free chat[/dim]"
        )

    console.print(table)


@app.command()
def quick(
    message: str = typer.Argument(help="Quick message to send to the agent")
):
    """
    Send a quick message to the agent without starting a full session.

    Examples:
        agent chat quick "What's the weather like?"
        agent chat quick "Help me write a Python function"
    """
    console.print(f"[blue]Sending quick message to agent...[/blue]")
    console.print(f"[dim]Message: {message}[/dim]\n")

    # Create a temporary session for this quick interaction
    session_id = f"quick-{uuid.uuid4()}"
    work_dir = Path.cwd() / ".agent_temp"

    asyncio.run(_quick_chat(message, work_dir, session_id))


async def _quick_chat(message: str, work_dir: Path, session_id: str):
    """Handle quick chat interaction with real agent."""
    import os

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]❌ Error: Please set OPENAI_API_KEY environment variable.[/red]")
        return

    try:
        # Import the real agent
        import sys
        from pathlib import Path as PathLib

        # Add directories to sys.path
        # __file__ is: .../capstone/agent_v2/cli/commands/chat.py
        # So we need to go up 4 levels to get to ai_solution_architecture
        current_file = PathLib(__file__)
        root_dir = current_file.parent.parent.parent.parent.parent  # chat.py -> commands -> cli -> agent_v2 -> capstone -> ai_solution_architecture

        # Paths resolved successfully

        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))

        from capstone.agent_v2.agent import Agent, AgentEventType, GENERIC_SYSTEM_PROMPT

        # Create agent for quick response
        agent = Agent.create_agent(
            name="AgentV2-Quick",
            description="Quick response agent",
            system_prompt=GENERIC_SYSTEM_PROMPT,
            mission=None,
            work_dir=str(work_dir.resolve()),
            llm=None,
        )

        response_captured = False

        with Live(Spinner("dots", text="Agent processing..."), console=console, refresh_per_second=4) as live:
            async for ev in agent.execute(user_message=message, session_id=session_id):
                if ev.type.name == AgentEventType.STATE_UPDATED.name:
                    state_data = ev.data
                    if 'response' in state_data:
                        live.stop()
                        console.print(f"\n[bold blue]🤖 Agent Response:[/bold blue]")
                        console.print(Panel(
                            Markdown(state_data['response']),
                            border_style="blue",
                            padding=(1, 2)
                        ))
                        response_captured = True
                        return

                elif ev.type.name == AgentEventType.COMPLETE.name:
                    live.stop()
                    completion_data = ev.data

                    # Try to get a meaningful response from completion data
                    if 'todolist' in completion_data:
                        todolist = completion_data['todolist']
                        if hasattr(todolist, 'items') and todolist.items:
                            # Show completed tasks
                            response = "✅ **Task completed successfully!**\n\n**What I did:**\n"
                            for i, item in enumerate(todolist.items, 1):
                                status = "✅" if item.status.name == 'COMPLETED' else "⏳"
                                response += f"{status} {i}. {item.task}\n"
                        else:
                            response = "✅ **Task completed successfully!**"
                    else:
                        response = "✅ **Task completed successfully!**"

                    console.print(f"\n[bold blue]🤖 Agent Response:[/bold blue]")
                    console.print(Panel(
                        Markdown(response),
                        border_style="green",
                        padding=(1, 2)
                    ))
                    response_captured = True
                    return

                elif ev.type.name == AgentEventType.TOOL_RESULT.name:
                    success = ev.data.get('success', False)
                    tool_result = ev.data.get('result', '')
                    tool_name = ev.data.get('tool', 'Tool')

                    if success and tool_result and len(str(tool_result)) < 500:
                        live.stop()
                        console.print(f"\n[bold blue]🤖 Agent Response:[/bold blue]")
                        console.print(Panel(
                            f"**Used {tool_name}:**\n\n```\n{tool_result}\n```",
                            border_style="blue",
                            padding=(1, 2)
                        ))
                        response_captured = True
                        return

        # Fallback if no response was captured
        if not response_captured:
            live.stop()
            console.print(f"\n[bold blue]🤖 Agent Response:[/bold blue]")
            console.print(Panel(
                "I processed your request. The task may have been completed in the background.\n\nCheck your working directory for any created files.",
                border_style="blue",
                padding=(1, 2)
            ))

    except Exception as e:
        console.print(f"\n[red]❌ Quick chat error: {e}[/red]")