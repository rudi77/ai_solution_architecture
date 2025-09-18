"""
Tests for configuration management.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from ..config.settings import CLISettings


class TestCLISettings:
    """Test CLISettings configuration class."""

    def test_default_settings(self):
        """Test default configuration values."""
        settings = CLISettings()

        assert settings.default_provider == "openai"
        assert settings.default_output_format == "table"
        assert settings.auto_confirm is False
        assert settings.show_progress is True
        assert settings.session_cleanup_days == 30

    def test_environment_variable_override(self):
        """Test environment variable configuration override."""
        with patch.dict('os.environ', {'AGENT_DEFAULT_PROVIDER': 'anthropic'}):
            settings = CLISettings()
            assert settings.default_provider == "anthropic"

    def test_save_and_load_config(self):
        """Test saving and loading configuration from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"

            # Create settings with custom values
            settings = CLISettings(
                default_provider="anthropic",
                auto_confirm=True,
                session_cleanup_days=7
            )

            # Save to file
            settings.save_to_file(config_path)
            assert config_path.exists()

            # Load from file
            loaded_settings = CLISettings.load_from_file(config_path)
            assert loaded_settings.default_provider == "anthropic"
            assert loaded_settings.auto_confirm is True
            assert loaded_settings.session_cleanup_days == 7

    def test_load_nonexistent_config(self):
        """Test loading configuration from non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "nonexistent.yaml"

            # Should return default settings
            settings = CLISettings.load_from_file(config_path)
            assert settings.default_provider == "openai"

    def test_update_setting(self):
        """Test updating individual settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"

            settings = CLISettings()
            with patch.object(settings, 'get_config_path', return_value=config_path):
                settings.update_setting("default_provider", "anthropic")

            assert settings.default_provider == "anthropic"
            assert config_path.exists()

    def test_update_invalid_setting(self):
        """Test updating non-existent setting raises error."""
        settings = CLISettings()

        with pytest.raises(ValueError, match="Unknown setting"):
            settings.update_setting("invalid_setting", "value")

    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"

            settings = CLISettings(
                default_provider="anthropic",
                auto_confirm=True
            )

            with patch.object(settings, 'get_config_path', return_value=config_path):
                settings.reset_to_defaults()

            assert settings.default_provider == "openai"
            assert settings.auto_confirm is False

    def test_export_config(self):
        """Test exporting configuration to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "exported_config.yaml"

            settings = CLISettings(default_provider="anthropic")
            settings.export_config(export_path)

            assert export_path.exists()

            # Verify exported content
            loaded_settings = CLISettings.load_from_file(export_path)
            assert loaded_settings.default_provider == "anthropic"

    def test_import_config(self):
        """Test importing configuration from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            import_path = Path(temp_dir) / "import_config.yaml"
            config_path = Path(temp_dir) / "main_config.yaml"

            # Create config to import
            import_settings = CLISettings(
                default_provider="anthropic",
                auto_confirm=True
            )
            import_settings.save_to_file(import_path)

            # Import into new settings
            settings = CLISettings()
            with patch.object(settings, 'get_config_path', return_value=config_path):
                settings.import_config(import_path)

            assert settings.default_provider == "anthropic"
            assert settings.auto_confirm is True

    @patch('pathlib.Path.home')
    def test_get_config_path(self, mock_home):
        """Test configuration path generation."""
        mock_home.return_value = Path("/fake/home")

        settings = CLISettings()
        config_path = settings.get_config_path()

        expected_path = Path("/fake/home/.agent/config.yaml")
        assert config_path == expected_path

    def test_list_type_setting(self):
        """Test handling of list-type settings."""
        settings = CLISettings()

        # Test default list values
        assert isinstance(settings.tool_discovery_paths, list)
        assert len(settings.tool_discovery_paths) > 0

        # Test updating list setting
        new_paths = ["/custom/path1", "/custom/path2"]
        settings.tool_discovery_paths = new_paths
        assert settings.tool_discovery_paths == new_paths

    def test_boolean_setting(self):
        """Test handling of boolean settings."""
        settings = CLISettings()

        # Test default boolean values
        assert isinstance(settings.auto_confirm, bool)
        assert settings.auto_confirm is False

        # Test updating boolean setting
        settings.auto_confirm = True
        assert settings.auto_confirm is True

    def test_integer_setting(self):
        """Test handling of integer settings."""
        settings = CLISettings()

        # Test default integer values
        assert isinstance(settings.session_cleanup_days, int)
        assert settings.session_cleanup_days == 30

        # Test updating integer setting
        settings.session_cleanup_days = 7
        assert settings.session_cleanup_days == 7

    def test_optional_string_setting(self):
        """Test handling of optional string settings."""
        settings = CLISettings()

        # Test default optional value
        assert settings.log_file is None

        # Test setting optional value
        settings.log_file = "/path/to/log"
        assert settings.log_file == "/path/to/log"