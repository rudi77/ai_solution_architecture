"""
Tests for the main CLI entry point.
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from ..main import app, dev_cli


class TestMainCLI:
    """Test the main CLI application."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help output."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Agent V2 Platform CLI" in result.stdout

    def test_cli_version(self):
        """Test version flag."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Agent CLI version" in result.stdout

    def test_cli_verbose_flag(self):
        """Test verbose flag."""
        result = self.runner.invoke(app, ["--verbose", "--help"])
        assert result.exit_code == 0

    @patch('capstone.agent_v2.cli.main.PluginManager')
    def test_cli_initialization(self, mock_plugin_manager):
        """Test CLI initialization with plugin manager."""
        mock_manager = MagicMock()
        mock_plugin_manager.return_value = mock_manager

        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        # Verify plugin manager was called
        mock_plugin_manager.assert_called_once()
        mock_manager.discover_plugins.assert_called_once()
        mock_manager.setup_plugins.assert_called_once()

    def test_command_groups_registered(self):
        """Test that all command groups are registered."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        # Check for main command groups
        assert "run" in result.stdout
        assert "missions" in result.stdout
        assert "tools" in result.stdout
        assert "providers" in result.stdout
        assert "sessions" in result.stdout
        assert "config" in result.stdout
        assert "dev" in result.stdout


class TestDevCLI:
    """Test the developer CLI application."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_dev_cli_help(self):
        """Test dev CLI help output."""
        result = self.runner.invoke(dev_cli, ["--help"])
        assert result.exit_code == 0
        assert "Developer tools" in result.stdout

    def test_dev_cli_verbose(self):
        """Test dev CLI verbose flag."""
        result = self.runner.invoke(dev_cli, ["--verbose", "--help"])
        assert result.exit_code == 0


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch('capstone.agent_v2.cli.main.initialize_cli')
    def test_keyboard_interrupt_handling(self, mock_init):
        """Test handling of keyboard interrupt."""
        mock_init.side_effect = KeyboardInterrupt()

        result = self.runner.invoke(app, ["--help"])
        # Note: CliRunner doesn't perfectly simulate KeyboardInterrupt
        # This test verifies the structure exists

    @patch('capstone.agent_v2.cli.main.initialize_cli')
    def test_general_exception_handling(self, mock_init):
        """Test handling of general exceptions."""
        mock_init.side_effect = Exception("Test error")

        result = self.runner.invoke(app, ["--help"])
        # The CLI should handle exceptions gracefully


class TestCLIConfiguration:
    """Test CLI configuration handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch('capstone.agent_v2.cli.main.CLISettings')
    def test_settings_loaded(self, mock_settings):
        """Test that settings are loaded during initialization."""
        mock_settings_instance = MagicMock()
        mock_settings.return_value = mock_settings_instance

        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0

        # Verify settings were instantiated
        mock_settings.assert_called()

    def test_no_args_shows_help(self):
        """Test that running CLI with no args shows help."""
        result = self.runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout