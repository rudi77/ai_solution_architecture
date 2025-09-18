"""
Configuration management for the CLI.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings
import yaml


class CLISettings(BaseSettings):
    """CLI configuration settings with environment variable support."""

    # Default provider
    default_provider: str = Field(default="openai", description="Default LLM provider")

    # Output preferences
    default_output_format: str = Field(default="table", description="Default output format")
    auto_confirm: bool = Field(default=False, description="Auto-confirm operations")
    show_progress: bool = Field(default=True, description="Show progress bars")
    color_output: bool = Field(default=True, description="Enable colored output")

    # Tool settings
    tool_discovery_paths: List[str] = Field(
        default_factory=lambda: ["./tools", "~/.agent/tools"],
        description="Paths to search for tools"
    )
    auto_install_tools: bool = Field(default=False, description="Auto-install missing tools")

    # Mission settings
    mission_template_paths: List[str] = Field(
        default_factory=lambda: ["./missions", "~/.agent/missions"],
        description="Paths to search for mission templates"
    )

    # Session settings
    session_cleanup_days: int = Field(default=30, description="Days to keep session data")
    session_storage_path: str = Field(default="~/.agent/sessions", description="Session storage path")

    # Debug settings
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    model_config = {
        "env_file": ".env",
        "env_prefix": "AGENT_",
        "case_sensitive": False
    }

    @classmethod
    def load_from_file(cls, config_path: Path) -> "CLISettings":
        """Load settings from a YAML configuration file."""
        if not config_path.exists():
            return cls()

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}

        return cls(**config_data)

    def save_to_file(self, config_path: Path) -> None:
        """Save settings to a YAML configuration file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = self.model_dump()
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

    def get_config_path(self) -> Path:
        """Get the default configuration file path."""
        config_dir = Path.home() / ".agent"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.yaml"

    def update_setting(self, key: str, value: Any) -> None:
        """Update a single setting and save to file."""
        if key in self.model_fields:
            setattr(self, key, value)
            self.save_to_file(self.get_config_path())
        else:
            raise ValueError(f"Unknown setting: {key}")

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        default_settings = self.__class__()
        for field_name in self.model_fields.keys():
            setattr(self, field_name, getattr(default_settings, field_name))
        self.save_to_file(self.get_config_path())

    def export_config(self, export_path: Path) -> None:
        """Export configuration to a file."""
        self.save_to_file(export_path)

    def import_config(self, import_path: Path) -> None:
        """Import configuration from a file."""
        imported_settings = self.load_from_file(import_path)
        for field_name in self.model_fields.keys():
            setattr(self, field_name, getattr(imported_settings, field_name))
        self.save_to_file(self.get_config_path())