"""
Rich-based CLI for IDP Pack - Template-Based Project Creation Interface
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.layout import Layout
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax

from capstone.examples.idp_pack.idp_tools import get_idp_tools
from capstone.prototype.agent import ReActAgent
from capstone.prototype.llm_provider import OpenAIProvider


class RichIDPCLI:
    """Rich-enhanced CLI for IDP Agent interactions."""
    
    def __init__(self):
        self.console = Console()
        self.agent: Optional[ReActAgent] = None
        self.session_id: Optional[str] = None
        
    def load_text(self, path: Path) -> str:
        """Load text file content."""
        return path.read_text(encoding="utf-8")
    
    async def initialize_agent(self) -> bool:
        """Initialize the ReAct agent with proper error handling."""
        try:
            root = Path(__file__).resolve().parents[2]
            mission_path = root / "examples" / "idp_pack" / "prompts" / "mission_template_git.txt"
            generic_path = root / "examples" / "idp_pack" / "system_prompt_idp.txt"
            orch_path = root / "examples" / "idp_pack" / "prompts" / "orchestrator.txt"
            
            if not mission_path.exists():
                self.console.print(f"[red]Error: Mission file not found at {mission_path}[/red]")
                return False
                
            template_mission = self.load_text(mission_path)
            system_prompt = self.load_text(generic_path)
            orch_mission = self.load_text(orch_path)
            openai_key = os.getenv("OPENAI_API_KEY")
            
            if not openai_key:
                self.console.print("[yellow]Warning: No OPENAI_API_KEY found. Using mock provider.[/yellow]")
            
            provider = OpenAIProvider(api_key=openai_key)

            # Build sub-agent with IDP tools (including templates and file tools)
            idp_tools = get_idp_tools()
            template_agent = ReActAgent(
                system_prompt=system_prompt,
                llm=provider,
                tools=idp_tools,
                mission=template_mission,
            )

            # Orchestrator only exposes the template agent tool
            self.agent = ReActAgent(
                system_prompt=system_prompt,
                llm=provider,
                tools=[
                    template_agent.to_tool(
                        name="agent_template_git",
                        description="Template-based project creation agent",
                        allowed_tools=[t.name for t in idp_tools],
                        budget={"max_steps": 20},
                        mission_override=template_mission,
                    )
                ],
                mission=orch_mission,
            )
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to initialize agent: {e}[/red]")
            return False
    
    def show_welcome(self):
        """Display welcome screen with Rich formatting."""
        welcome_panel = Panel(
            Text.from_markup(
                "[bold blue]IDP Pack CLI[/bold blue]\n"
                "[dim]Intelligent Development Partner - Template-Based Project Creation[/dim]\n\n"
                "[green]Features:[/green]\n"
                "• Create repositories with AI-generated project templates\n"
                "• Intelligent template selection with clarification\n"
                "• Complete project structure generation\n"
                "• Git integration with commit and push\n\n"
                "[green]Commands:[/green]\n"
                "• Type your request naturally\n"
                "• [bold]help[/bold] - Show available commands\n"
                "• [bold]status[/bold] - Show current session status\n"
                "• [bold]clear[/bold] - Clear session history\n"
                "• [bold]exit/quit/q[/bold] - Exit the CLI\n\n"
                "[yellow]Ready to create your next project![/yellow]"
            ),
            title="🚀 Welcome",
            border_style="blue",
            padding=(1, 2)
        )
        self.console.print(welcome_panel)
    
    def show_status(self):
        """Show current session status."""
        table = Table(title="Session Status", show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        table.add_row("Session ID", str(self.session_id) if self.session_id else "None")
        table.add_row("Agent Status", "Ready" if self.agent else "Not initialized")
        table.add_row("OpenAI Key", "✅ Set" if os.getenv("OPENAI_API_KEY") else "❌ Not set")
        
        self.console.print(table)
    
    def show_help(self):
        """Display help information."""
        help_content = """
        # IDP Pack CLI Help
        
        ## Available Commands
        - **help** - Show this help message
        - **status** - Display current session information
        - **clear** - Clear the current session and start fresh
        - **exit/quit/q** - Exit the CLI
        
        ## Template-Based Project Creation Examples
        - "Create Python FastAPI service named payment-api"
        - "Create Python web application named user-service" 
        - "Create C# Web API named order-service"
        - "Create microservice with hexagonal architecture named product-api"
        
        ## Available Templates
        - **Python FastAPI Hexagonal** - Microservice with Hexagonal Architecture
        - **Python Flask MVC** - Web application with MVC pattern
        - **C# Web API Clean** - Enterprise API with Clean Architecture + CQRS
        
        ## How It Works
        1. **Repository Creation** - Creates Git repo locally and on GitHub
        2. **Template Selection** - Intelligently matches your request to templates
        3. **Clarification** - Asks for choice if multiple templates match
        4. **Code Generation** - Creates complete project structure
        5. **Git Integration** - Commits and pushes generated code
        
        ## Tips
        - Use natural language to describe your project
        - Specify language, framework, and architecture preferences
        - The agent will ask for clarification if needed
        - Session history is maintained for context
        """
        self.console.print(Markdown(help_content))
    
    async def process_user_input(self, user_input: str) -> bool:
        """Process user input and handle agent responses."""
        # Handle built-in commands
        if user_input.lower() in {"exit", "quit", "q"}:
            return False
        elif user_input.lower() == "help":
            self.show_help()
            return True
        elif user_input.lower() == "status":
            self.show_status()
            return True
        elif user_input.lower() == "clear":
            self.session_id = None
            self.console.print("[green]Session cleared![/green]")
            return True
        
        # Process with agent
        if not self.agent:
            self.console.print("[red]Agent not initialized![/red]")
            return True
        
        # Show processing indicator
        with Live(Spinner("dots", text="Processing..."), console=self.console) as live:
            try:
                response_text = ""
                async for update in self.agent.process_request(user_input, session_id=self.session_id):
                    response_text += update
                
                # Update session ID
                self.session_id = self.agent.session_id
                
                # Display response in a panel
                if response_text.strip():
                    response_panel = Panel(
                        response_text.strip(),
                        title="🤖 Agent Response",
                        border_style="green",
                        padding=(1, 2)
                    )
                    live.stop()
                    self.console.print(response_panel)
                
                # Check if awaiting user input
                if self.agent.context.get("awaiting_user_input"):
                    self.console.print("[yellow]Agent is awaiting additional input...[/yellow]")
                
            except Exception as e:
                live.stop()
                self.console.print(f"[red]Error processing request: {e}[/red]")
        
        return True
    
    async def run(self):
        """Main CLI loop."""
        self.show_welcome()
        
        # Initialize agent
        if not await self.initialize_agent():
            self.console.print("[red]Failed to initialize. Exiting.[/red]")
            return
        
        self.console.print("[green]✅ Agent initialized successfully![/green]\n")
        
        # Main interaction loop
        while True:
            try:
                user_input = Prompt.ask(
                    "[bold cyan]You[/bold cyan]",
                    console=self.console
                ).strip()
                
                if not user_input:
                    continue
                
                should_continue = await self.process_user_input(user_input)
                if not should_continue:
                    break
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted by user[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Unexpected error: {e}[/red]")
                break
        
        # Goodbye message
        goodbye_panel = Panel(
            "[bold blue]Thank you for using IDP Pack CLI![/bold blue]\n"
            "[dim]Your intelligent development partner[/dim]",
            title="👋 Goodbye",
            border_style="blue"
        )
        self.console.print(goodbye_panel)


async def main():
    """Entry point for the Rich IDP CLI."""
    cli = RichIDPCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())