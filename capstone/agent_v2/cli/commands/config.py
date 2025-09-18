"""
Config command group for managing configuration.
"""

from pathlib import Path
from typing import Optional, Any

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from ..config.settings import CLISettings
from ..output_formatter import OutputFormat, OutputFormatter

console = Console()
app = typer.Typer(help="Manage configuration")


def complete_config_keys(incomplete: str):
    """Auto-complete configuration keys."""
    settings = CLISettings()
    return list(settings.__fields__.keys())


@app.command("show")
def show_config(
    output_format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output", "-o",
        help="Output format"
    ),
    show_sensitive: bool = typer.Option(
        False,
        "--show-sensitive",
        help="Show sensitive values (like API keys)"
    ),
):
    """
    Show current configuration.

    Examples:
        agent config show
        agent config show --output yaml
        agent config show --show-sensitive
    """
    settings = CLISettings()
    config_data = settings.model_dump()

    # Mask sensitive values unless explicitly requested
    if not show_sensitive:
        sensitive_keys = ["api_key", "password", "secret", "token"]
        for key, value in config_data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if value:
                    config_data[key] = "*" * min(len(str(value)), 8)

    if output_format == OutputFormat.TABLE:
        table = Table(title="CLI Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Description", style="dim")

        # Get field descriptions from the model
        for field_name, field_info in settings.model_fields.items():
            value = config_data.get(field_name, "")
            description = field_info.description or ""

            # Format lists and complex values
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = str(value)

            table.add_row(field_name, str(value), description)

        console.print(table)
    else:
        OutputFormatter.format_data(config_data, output_format, "CLI Configuration")


@app.command("set")
def set_config(
    key: str = typer.Argument(
        help="Configuration key",
        autocompletion=complete_config_keys
    ),
    value: str = typer.Argument(help="Configuration value"),
):
    """
    Set a configuration value.

    Examples:
        agent config set default_provider anthropic
        agent config set auto_confirm true
        agent config set session_cleanup_days 7
    """
    settings = CLISettings()

    # Validate key exists
    if key not in settings.model_fields:
        console.print(f"[red]Error: Unknown configuration key '{key}'[/red]")
        console.print("Available keys:")
        for field_name in settings.model_fields.keys():
            console.print(f"  - {field_name}")
        raise typer.Exit(1)

    # Convert value to appropriate type
    field_info = settings.model_fields[key]
    field_type = field_info.annotation

    try:
        if field_type == bool:
            converted_value = value.lower() in ("true", "1", "yes", "on")
        elif field_type == int:
            converted_value = int(value)
        elif field_type == float:
            converted_value = float(value)
        elif hasattr(field_type, '__origin__') and field_type.__origin__ is list:
            # Handle lists - split by comma
            converted_value = [item.strip() for item in value.split(",")]
        else:
            converted_value = value
    except ValueError as e:
        console.print(f"[red]Error: Invalid value '{value}' for {key}: {e}[/red]")
        raise typer.Exit(1)

    try:
        settings.update_setting(key, converted_value)
        console.print(f"[green]✓ Set {key} = {converted_value}[/green]")
    except Exception as e:
        console.print(f"[red]Error updating configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command("reset")
def reset_config(
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Skip confirmation prompt"
    ),
):
    """
    Reset configuration to defaults.

    Examples:
        agent config reset
        agent config reset --confirm
    """
    if not confirm:
        if not Confirm.ask("Reset all configuration to defaults?"):
            console.print("[yellow]Reset cancelled[/yellow]")
            return

    settings = CLISettings()
    settings.reset_to_defaults()

    console.print("[green]✓ Configuration reset to defaults[/green]")


@app.command("export")
def export_config(
    file: Path = typer.Argument(help="Export file path"),
    format: str = typer.Option(
        "yaml",
        "--format", "-f",
        help="Export format (yaml, json)"
    ),
):
    """
    Export configuration to file.

    Examples:
        agent config export config-backup.yaml
        agent config export config.json --format json
    """
    settings = CLISettings()

    try:
        if format == "yaml":
            settings.export_config(file)
        elif format == "json":
            import json
            config_data = settings.model_dump()
            with open(file, 'w') as f:
                json.dump(config_data, f, indent=2)
        else:
            console.print(f"[red]Error: Unsupported format '{format}'[/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓ Configuration exported to {file}[/green]")
    except Exception as e:
        console.print(f"[red]Error exporting configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command("import")
def import_config(
    file: Path = typer.Argument(help="Import file path"),
    merge: bool = typer.Option(
        False,
        "--merge",
        help="Merge with existing configuration instead of replacing"
    ),
):
    """
    Import configuration from file.

    Examples:
        agent config import config-backup.yaml
        agent config import partial-config.yaml --merge
    """
    if not file.exists():
        console.print(f"[red]Error: Configuration file not found: {file}[/red]")
        raise typer.Exit(1)

    try:
        settings = CLISettings()

        if merge:
            # Load existing settings and merge
            existing_config = settings.model_dump()
            imported_settings = CLISettings.load_from_file(file)
            imported_config = imported_settings.model_dump()

            # Merge configurations
            for key, value in imported_config.items():
                if key in settings.__fields__:
                    existing_config[key] = value

            # Create new settings with merged data
            merged_settings = CLISettings(**existing_config)
            merged_settings.save_to_file(settings.get_config_path())
        else:
            # Replace entire configuration
            settings.import_config(file)

        console.print(f"[green]✓ Configuration imported from {file}[/green]")
        if merge:
            console.print("[dim]Configurations were merged[/dim]")
    except Exception as e:
        console.print(f"[red]Error importing configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command("validate")
def validate_config():
    """
    Validate current configuration.

    Examples:
        agent config validate
    """
    try:
        settings = CLISettings()
        config_path = settings.get_config_path()

        console.print("[blue]Validating configuration...[/blue]")

        # Basic validation - try to create settings object
        CLISettings.load_from_file(config_path)

        # TODO: Add more specific validations:
        # - Check if paths exist
        # - Validate provider configurations
        # - Test tool discovery paths
        # - Verify format values are valid

        console.print("[green]✓ Configuration is valid[/green]")

    except Exception as e:
        console.print(f"[red]Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command("path")
def show_config_path():
    """
    Show configuration file path.

    Examples:
        agent config path
    """
    settings = CLISettings()
    config_path = settings.get_config_path()

    console.print(f"[blue]Configuration file:[/blue] {config_path}")

    if config_path.exists():
        console.print("[green]✓ File exists[/green]")
    else:
        console.print("[yellow]⚠ File does not exist (will be created on first save)[/yellow]")