"""
Tests for plugin management system.
"""

import pytest
from unittest.mock import patch, MagicMock
import pkg_resources

import typer

from ..plugin_manager import PluginManager, CLIPlugin


class MockPlugin(CLIPlugin):
    """Mock plugin for testing."""

    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def command_group(self) -> typer.Typer:
        app = typer.Typer(name="test", help="Test plugin")

        @app.command()
        def hello():
            """Test command."""
            print("Hello from test plugin")

        return app

    def setup(self, main_app: typer.Typer) -> None:
        """Setup test plugin."""
        pass


class InvalidPlugin:
    """Invalid plugin that doesn't inherit from CLIPlugin."""

    def name(self):
        return "invalid"


class TestCLIPlugin:
    """Test the CLIPlugin base class."""

    def test_cli_plugin_is_abstract(self):
        """Test that CLIPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CLIPlugin()

    def test_mock_plugin_implementation(self):
        """Test mock plugin implementation."""
        plugin = MockPlugin()

        assert plugin.name == "test-plugin"
        assert isinstance(plugin.command_group, typer.Typer)

        # Test setup method
        mock_app = MagicMock()
        plugin.setup(mock_app)  # Should not raise exception


class TestPluginManager:
    """Test the PluginManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.plugin_manager = PluginManager()

    def test_plugin_manager_initialization(self):
        """Test PluginManager initialization."""
        assert isinstance(self.plugin_manager.plugins, dict)
        assert isinstance(self.plugin_manager.loaded_plugins, list)
        assert len(self.plugin_manager.plugins) == 0
        assert len(self.plugin_manager.loaded_plugins) == 0

    def test_register_plugin(self):
        """Test plugin registration."""
        plugin = MockPlugin()

        with patch('rich.console.Console.print') as mock_print:
            self.plugin_manager.register_plugin(plugin)

        assert "test-plugin" in self.plugin_manager.plugins
        assert self.plugin_manager.plugins["test-plugin"] == plugin
        mock_print.assert_called_once()

    def test_register_invalid_plugin(self):
        """Test registration of invalid plugin."""
        invalid_plugin = InvalidPlugin()

        with pytest.raises(ValueError, match="Plugin must inherit from CLIPlugin"):
            self.plugin_manager.register_plugin(invalid_plugin)

    def test_register_duplicate_plugin(self):
        """Test registration of duplicate plugin."""
        plugin = MockPlugin()

        # Register first time
        self.plugin_manager.register_plugin(plugin)

        # Register again - should warn but not error
        with patch('rich.console.Console.print') as mock_print:
            self.plugin_manager.register_plugin(plugin)

        # Should still have only one plugin
        assert len(self.plugin_manager.plugins) == 1
        mock_print.assert_called()

    def test_get_plugin(self):
        """Test getting plugin by name."""
        plugin = MockPlugin()
        self.plugin_manager.register_plugin(plugin)

        retrieved_plugin = self.plugin_manager.get_plugin("test-plugin")
        assert retrieved_plugin == plugin

        # Test non-existent plugin
        non_existent = self.plugin_manager.get_plugin("non-existent")
        assert non_existent is None

    def test_list_plugins(self):
        """Test listing loaded plugins."""
        plugin = MockPlugin()
        self.plugin_manager.register_plugin(plugin)

        plugin_names = self.plugin_manager.list_plugins()
        assert "test-plugin" in plugin_names
        assert len(plugin_names) == 1

    def test_setup_plugins(self):
        """Test setting up plugins with main app."""
        plugin = MockPlugin()
        self.plugin_manager.register_plugin(plugin)

        mock_app = MagicMock()

        with patch('rich.console.Console.print'):
            self.plugin_manager.setup_plugins(mock_app)

        # Verify setup was called
        mock_app.add_typer.assert_called_once()

    def test_setup_plugins_with_error(self):
        """Test plugin setup with error handling."""
        # Create a plugin that raises an error during setup
        class ErrorPlugin(CLIPlugin):
            @property
            def name(self):
                return "error-plugin"

            @property
            def command_group(self):
                return typer.Typer()

            def setup(self, main_app):
                raise Exception("Setup error")

        error_plugin = ErrorPlugin()
        self.plugin_manager.register_plugin(error_plugin)

        mock_app = MagicMock()

        with patch('rich.console.Console.print') as mock_print:
            self.plugin_manager.setup_plugins(mock_app)

        # Should print warning about failed setup
        mock_print.assert_called()

    @patch('pkg_resources.iter_entry_points')
    def test_discover_plugins_success(self, mock_iter_entry_points):
        """Test successful plugin discovery."""
        # Mock entry point
        mock_entry_point = MagicMock()
        mock_entry_point.name = "test-plugin"
        mock_entry_point.load.return_value = MockPlugin
        mock_iter_entry_points.return_value = [mock_entry_point]

        with patch('rich.console.Console.print'):
            self.plugin_manager.discover_plugins()

        assert "test-plugin" in self.plugin_manager.plugins
        assert "test-plugin" in self.plugin_manager.loaded_plugins

    @patch('pkg_resources.iter_entry_points')
    def test_discover_plugins_load_error(self, mock_iter_entry_points):
        """Test plugin discovery with load error."""
        # Mock entry point that raises error
        mock_entry_point = MagicMock()
        mock_entry_point.name = "error-plugin"
        mock_entry_point.load.side_effect = Exception("Load error")
        mock_iter_entry_points.return_value = [mock_entry_point]

        with patch('rich.console.Console.print') as mock_print:
            self.plugin_manager.discover_plugins()

        # Should handle error gracefully
        assert len(self.plugin_manager.plugins) == 0
        mock_print.assert_called()

    @patch('pkg_resources.iter_entry_points')
    def test_discover_plugins_no_entry_points(self, mock_iter_entry_points):
        """Test plugin discovery when no entry points exist."""
        mock_iter_entry_points.side_effect = Exception("No entry points")

        # Should handle gracefully
        self.plugin_manager.discover_plugins()
        assert len(self.plugin_manager.plugins) == 0

    def test_multiple_plugins(self):
        """Test managing multiple plugins."""
        class SecondPlugin(CLIPlugin):
            @property
            def name(self):
                return "second-plugin"

            @property
            def command_group(self):
                return typer.Typer()

            def setup(self, main_app):
                pass

        plugin1 = MockPlugin()
        plugin2 = SecondPlugin()

        self.plugin_manager.register_plugin(plugin1)
        self.plugin_manager.register_plugin(plugin2)

        assert len(self.plugin_manager.plugins) == 2
        assert "test-plugin" in self.plugin_manager.plugins
        assert "second-plugin" in self.plugin_manager.plugins

        plugin_names = self.plugin_manager.list_plugins()
        assert len(plugin_names) == 2
        assert "test-plugin" in plugin_names
        assert "second-plugin" in plugin_names