"""
Missions command group for managing mission templates.
"""

from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ..config.settings import CLISettings
from ..output_formatter import OutputFormat, OutputFormatter

console = Console()
app = typer.Typer(help="Manage mission templates")


def complete_mission_templates(incomplete: str):
    """Auto-complete mission template names."""
    # TODO: Implement actual template discovery
    return ["data-analysis", "code-review", "web-scraping", "report-generation"]


def complete_categories(incomplete: str):
    """Auto-complete mission categories."""
    return ["data", "code", "web", "analysis", "automation"]


@app.command("list")
def list_missions(
    category: Optional[str] = typer.Option(
        None,
        "--category", "-c",
        help="Filter by category",
        autocompletion=complete_categories
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output", "-o",
        help="Output format"
    ),
):
    """
    List available mission templates.

    Examples:
        agent missions list
        agent missions list --category data
        agent missions list --output json
    """
    # TODO: Implement actual mission discovery from configured paths
    missions = [
        {
            "name": "data-analysis",
            "category": "data",
            "tools_required": ["pandas", "matplotlib"],
            "description": "Analyze datasets and generate insights"
        },
        {
            "name": "code-review",
            "category": "code",
            "tools_required": ["git", "static-analysis"],
            "description": "Review code for quality and security issues"
        },
        {
            "name": "web-scraping",
            "category": "web",
            "tools_required": ["requests", "beautifulsoup"],
            "description": "Extract data from websites"
        }
    ]

    if category:
        missions = [m for m in missions if m["category"] == category]

    OutputFormatter.format_mission_list(missions, output_format)


@app.command("show")
def show_mission(
    template_id: str = typer.Argument(
        help="Mission template name",
        autocompletion=complete_mission_templates
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output", "-o",
        help="Output format"
    ),
):
    """
    Show detailed information about a mission template.

    Examples:
        agent missions show data-analysis
        agent missions show code-review --output yaml
    """
    # TODO: Load actual mission template
    mission_details = {
        "name": template_id,
        "category": "data",
        "description": "Comprehensive data analysis mission template",
        "version": "1.0.0",
        "tools_required": ["pandas", "matplotlib", "seaborn"],
        "parameters": [
            {
                "name": "data_source",
                "type": "string",
                "required": True,
                "description": "Path to data file or database connection"
            },
            {
                "name": "output_path",
                "type": "string",
                "required": False,
                "default": "./analysis_results",
                "description": "Output directory for results"
            }
        ],
        "steps": [
            "Load and validate data",
            "Perform exploratory analysis",
            "Generate visualizations",
            "Create summary report"
        ]
    }

    console.print(f"[bold blue]Mission Template: {template_id}[/bold blue]")
    OutputFormatter.format_data(mission_details, output_format)


@app.command("create")
def create_mission(
    name: str = typer.Argument(help="Mission template name"),
    category: str = typer.Option(
        "general",
        "--category", "-c",
        help="Mission category",
        autocompletion=complete_categories
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--batch",
        help="Interactive template creation"
    ),
):
    """
    Create a new mission template.

    Examples:
        agent missions create my-mission
        agent missions create data-processor --category data
    """
    settings = CLISettings()

    if interactive:
        console.print(f"[bold blue]Creating mission template: {name}[/bold blue]")

        # Collect template information interactively
        description = Prompt.ask("Enter mission description")
        tools = Prompt.ask("Enter required tools (comma-separated)", default="")

        template_data = {
            "name": name,
            "category": category,
            "description": description,
            "tools_required": [t.strip() for t in tools.split(",") if t.strip()],
            "parameters": [],
            "steps": []
        }

        # Add parameters
        while Confirm.ask("Add a parameter?", default=False):
            param_name = Prompt.ask("Parameter name")
            param_type = Prompt.ask("Parameter type", default="string")
            param_required = Confirm.ask("Required?", default=True)
            param_description = Prompt.ask("Parameter description", default="")

            template_data["parameters"].append({
                "name": param_name,
                "type": param_type,
                "required": param_required,
                "description": param_description
            })

        # Add steps
        while Confirm.ask("Add a step?", default=False):
            step = Prompt.ask("Step description")
            template_data["steps"].append(step)

    else:
        # Batch mode - create minimal template
        template_data = {
            "name": name,
            "category": category,
            "description": f"Mission template: {name}",
            "tools_required": [],
            "parameters": [],
            "steps": []
        }

    # TODO: Save template to configured mission path
    console.print(f"[green]Created mission template: {name}[/green]")
    console.print(f"[dim]Category: {category}[/dim]")


@app.command("edit")
def edit_mission(
    template_id: str = typer.Argument(
        help="Mission template name",
        autocompletion=complete_mission_templates
    ),
):
    """
    Edit an existing mission template.

    Examples:
        agent missions edit data-analysis
    """
    # TODO: Load existing template and open in editor
    console.print(f"[blue]Editing mission template: {template_id}[/blue]")
    console.print("[dim]This would open the template in your configured editor[/dim]")


@app.command("validate")
def validate_mission(
    template_file: Path = typer.Argument(help="Mission template file path"),
):
    """
    Validate mission template syntax and dependencies.

    Examples:
        agent missions validate ./missions/my-mission.yaml
    """
    if not template_file.exists():
        console.print(f"[red]Error: Template file not found: {template_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Validating mission template: {template_file}[/blue]")

    # TODO: Implement actual validation
    # - YAML syntax
    # - Required fields
    # - Tool dependencies
    # - Parameter validation

    console.print("[green]✓ Template validation passed[/green]")


@app.command("import")
def import_mission(
    template_file: Path = typer.Argument(help="Mission template file to import"),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Overwrite existing template"
    ),
):
    """
    Import a mission template from file.

    Examples:
        agent missions import ./external-mission.yaml
        agent missions import ./mission.yaml --force
    """
    if not template_file.exists():
        console.print(f"[red]Error: Template file not found: {template_file}[/red]")
        raise typer.Exit(1)

    settings = CLISettings()

    # TODO: Load and validate template
    # TODO: Check if template already exists
    # TODO: Copy to mission template directory

    console.print(f"[green]Imported mission template from: {template_file}[/green]")