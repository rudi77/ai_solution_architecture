"""
Plugin management system for the CLI.
"""

import pkg_resources
from abc import ABC, abstractmethod
from typing import Dict, List

import typer
from rich.console import Console

console = Console()


class CLIPlugin(ABC):
    """Base class for CLI plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name for registration."""
        pass

    @property
    @abstractmethod
    def command_group(self) -> typer.Typer:
        """Typer app with plugin commands."""
        pass

    @abstractmethod
    def setup(self, main_app: typer.Typer) -> None:
        """Setup plugin with main CLI app."""
        pass


class PluginManager:
    """Manages CLI plugins and their registration."""

    def __init__(self):
        self.plugins: Dict[str, CLIPlugin] = {}
        self.loaded_plugins: List[str] = []

    def discover_plugins(self):
        """Auto-discover plugins from installed packages."""
        try:
            for entry_point in pkg_resources.iter_entry_points('agent_cli_plugins'):
                try:
                    plugin_class = entry_point.load()
                    plugin = plugin_class()
                    self.register_plugin(plugin)
                    self.loaded_plugins.append(entry_point.name)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to load plugin {entry_point.name}: {e}[/yellow]")
        except Exception as e:
            # If no plugins are found or entry points don't exist, that's fine
            pass

    def register_plugin(self, plugin: CLIPlugin):
        """Register a plugin with the CLI."""
        if not isinstance(plugin, CLIPlugin):
            raise ValueError(f"Plugin must inherit from CLIPlugin, got {type(plugin)}")

        if plugin.name in self.plugins:
            console.print(f"[yellow]Warning: Plugin {plugin.name} already registered[/yellow]")
            return

        self.plugins[plugin.name] = plugin
        console.print(f"[dim]Registered plugin: {plugin.name}[/dim]")

    def setup_plugins(self, main_app: typer.Typer):
        """Setup all registered plugins."""
        for plugin in self.plugins.values():
            try:
                plugin.setup(main_app)
                main_app.add_typer(plugin.command_group, name=plugin.name)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to setup plugin {plugin.name}: {e}[/yellow]")

    def list_plugins(self) -> List[str]:
        """Get list of loaded plugin names."""
        return list(self.plugins.keys())

    def get_plugin(self, name: str) -> CLIPlugin:
        """Get a specific plugin by name."""
        return self.plugins.get(name)