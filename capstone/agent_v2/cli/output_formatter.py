"""
Output formatting system for the CLI.
"""

import json
from enum import Enum
from typing import Any, List, Dict, Union

import yaml
from rich.console import Console
from rich.json import JSON
from rich.table import Table
from rich.text import Text

console = Console()


class OutputFormat(Enum):
    """Available output formats."""
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    TEXT = "text"


class OutputFormatter:
    """Handles formatting output in different formats."""

    @staticmethod
    def format_data(data: Any, format_type: OutputFormat, title: str = None) -> None:
        """Format and display data in the specified format."""
        if format_type == OutputFormat.TABLE:
            OutputFormatter._format_table(data, title)
        elif format_type == OutputFormat.JSON:
            OutputFormatter._format_json(data)
        elif format_type == OutputFormat.YAML:
            OutputFormatter._format_yaml(data)
        elif format_type == OutputFormat.TEXT:
            OutputFormatter._format_text(data)

    @staticmethod
    def _format_table(data: Any, title: str = None) -> None:
        """Format data as a Rich table."""
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            # List of dictionaries - create table
            table = Table(title=title)

            # Add columns from first item
            for key in data[0].keys():
                table.add_column(key.replace('_', ' ').title(), style="cyan")

            # Add rows
            for item in data:
                row_values = []
                for value in item.values():
                    if isinstance(value, (list, dict)):
                        row_values.append(str(value))
                    else:
                        row_values.append(str(value) if value is not None else "")
                table.add_row(*row_values)

            console.print(table)

        elif isinstance(data, dict):
            # Single dictionary - create key-value table
            table = Table(title=title, show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value) if value is not None else ""
                table.add_row(key.replace('_', ' ').title(), value_str)

            console.print(table)

        else:
            # Fallback to text format
            console.print(str(data))

    @staticmethod
    def _format_json(data: Any) -> None:
        """Format data as JSON."""
        if hasattr(data, 'model_dump'):
            # Pydantic model
            json_data = data.model_dump()
        elif isinstance(data, list) and len(data) > 0 and hasattr(data[0], 'model_dump'):
            # List of Pydantic models
            json_data = [item.model_dump() for item in data]
        else:
            json_data = data

        console.print(JSON.from_data(json_data))

    @staticmethod
    def _format_yaml(data: Any) -> None:
        """Format data as YAML."""
        if hasattr(data, 'model_dump'):
            # Pydantic model
            yaml_data = data.model_dump()
        elif isinstance(data, list) and len(data) > 0 and hasattr(data[0], 'model_dump'):
            # List of Pydantic models
            yaml_data = [item.model_dump() for item in data]
        else:
            yaml_data = data

        yaml_str = yaml.dump(yaml_data, default_flow_style=False, indent=2)
        console.print(yaml_str)

    @staticmethod
    def _format_text(data: Any) -> None:
        """Format data as plain text."""
        if isinstance(data, list):
            for item in data:
                console.print(str(item))
        else:
            console.print(str(data))

    @staticmethod
    def format_mission_list(missions: List[Dict], format_type: OutputFormat) -> None:
        """Format mission list with specific styling."""
        if format_type == OutputFormat.TABLE:
            table = Table(title="Available Missions")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Category", style="green")
            table.add_column("Tools Required", style="yellow")
            table.add_column("Description", style="white")

            for mission in missions:
                tools = ", ".join(mission.get('tools_required', []))
                description = mission.get('description', '')
                if len(description) > 50:
                    description = description[:47] + "..."

                table.add_row(
                    mission.get('name', ''),
                    mission.get('category', ''),
                    tools,
                    description
                )

            console.print(table)
        else:
            OutputFormatter.format_data(missions, format_type)

    @staticmethod
    def format_tool_list(tools: List[Dict], format_type: OutputFormat) -> None:
        """Format tool list with specific styling."""
        if format_type == OutputFormat.TABLE:
            table = Table(title="Available Tools")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Version", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Description", style="white")

            for tool in tools:
                status = "[green]✅ Installed[/green]" if tool.get('installed', False) else "[red]❌ Not Installed[/red]"
                description = tool.get('description', '')
                if len(description) > 50:
                    description = description[:47] + "..."

                table.add_row(
                    tool.get('name', ''),
                    tool.get('version', ''),
                    status,
                    description
                )

            console.print(table)
        else:
            OutputFormatter.format_data(tools, format_type)

    @staticmethod
    def format_provider_list(providers: List[Dict], format_type: OutputFormat) -> None:
        """Format provider list with specific styling."""
        if format_type == OutputFormat.TABLE:
            table = Table(title="LLM Providers")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Type", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Default", style="blue")

            for provider in providers:
                status = "[green]✅ Connected[/green]" if provider.get('connected', False) else "[red]❌ Not Connected[/red]"
                is_default = "[blue]⭐ Yes[/blue]" if provider.get('is_default', False) else ""

                table.add_row(
                    provider.get('name', ''),
                    provider.get('type', ''),
                    status,
                    is_default
                )

            console.print(table)
        else:
            OutputFormatter.format_data(providers, format_type)

    @staticmethod
    def format_session_list(sessions: List[Dict], format_type: OutputFormat) -> None:
        """Format session list with specific styling."""
        if format_type == OutputFormat.TABLE:
            table = Table(title="Execution Sessions")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Mission", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Started", style="blue")
            table.add_column("Duration", style="white")

            for session in sessions:
                table.add_row(
                    session.get('id', '')[:8] + "...",  # Truncate ID
                    session.get('mission', ''),
                    session.get('status', ''),
                    session.get('started', ''),
                    session.get('duration', '')
                )

            console.print(table)
        else:
            OutputFormatter.format_data(sessions, format_type)