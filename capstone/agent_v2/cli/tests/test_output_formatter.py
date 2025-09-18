"""
Tests for output formatting system.
"""

import pytest
import json
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from ..output_formatter import OutputFormatter, OutputFormat


class TestOutputFormatter:
    """Test the OutputFormatter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data = [
            {"name": "test1", "value": 100, "status": "active"},
            {"name": "test2", "value": 200, "status": "inactive"}
        ]

        self.single_data = {"name": "test", "value": 100, "status": "active"}

    def test_format_table_list_of_dicts(self):
        """Test formatting list of dictionaries as table."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(self.test_data, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_format_table_single_dict(self):
        """Test formatting single dictionary as table."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(self.single_data, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_format_json(self):
        """Test JSON formatting."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(self.test_data, OutputFormat.JSON)
            mock_print.assert_called_once()

    def test_format_yaml(self):
        """Test YAML formatting."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(self.test_data, OutputFormat.YAML)
            mock_print.assert_called_once()

    def test_format_text(self):
        """Test text formatting."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(self.test_data, OutputFormat.TEXT)
            # Should be called for each item in the list
            assert mock_print.call_count == len(self.test_data)

    def test_format_mission_list(self):
        """Test mission-specific formatting."""
        missions = [
            {
                "name": "mission1",
                "category": "data",
                "tools_required": ["tool1", "tool2"],
                "description": "Test mission"
            }
        ]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_mission_list(missions, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_format_tool_list(self):
        """Test tool-specific formatting."""
        tools = [
            {
                "name": "tool1",
                "version": "1.0.0",
                "installed": True,
                "description": "Test tool"
            }
        ]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_tool_list(tools, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_format_provider_list(self):
        """Test provider-specific formatting."""
        providers = [
            {
                "name": "openai",
                "type": "openai",
                "connected": True,
                "is_default": True
            }
        ]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_provider_list(providers, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_format_session_list(self):
        """Test session-specific formatting."""
        sessions = [
            {
                "id": "sess-123",
                "mission": "test-mission",
                "status": "completed",
                "started": "2025-01-18 10:00:00",
                "duration": "5m"
            }
        ]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_session_list(sessions, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_table_with_title(self):
        """Test table formatting with title."""
        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(
                self.test_data,
                OutputFormat.TABLE,
                title="Test Title"
            )
            mock_print.assert_called_once()

    def test_format_pydantic_models(self):
        """Test formatting Pydantic models."""
        # Mock Pydantic-like object
        class MockModel:
            def model_dump(self):
                return {"name": "test", "value": 100}

        mock_model = MockModel()

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(mock_model, OutputFormat.JSON)
            mock_print.assert_called_once()

    def test_format_list_of_pydantic_models(self):
        """Test formatting list of Pydantic models."""
        class MockModel:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def model_dump(self):
                return {"name": self.name, "value": self.value}

        models = [MockModel("test1", 100), MockModel("test2", 200)]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(models, OutputFormat.JSON)
            mock_print.assert_called_once()

    def test_handle_none_values(self):
        """Test handling of None values in data."""
        data_with_none = {"name": "test", "value": None, "status": "active"}

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(data_with_none, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_handle_complex_values(self):
        """Test handling of complex values (lists, dicts) in table format."""
        complex_data = {
            "name": "test",
            "config": {"key": "value"},
            "tags": ["tag1", "tag2"]
        }

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(complex_data, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_long_description_truncation(self):
        """Test truncation of long descriptions in mission/tool lists."""
        long_description = "x" * 100  # 100 character description

        missions = [{
            "name": "mission1",
            "category": "data",
            "tools_required": [],
            "description": long_description
        }]

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_mission_list(missions, OutputFormat.TABLE)
            mock_print.assert_called_once()

    def test_fallback_to_string(self):
        """Test fallback to string conversion for unsupported data types."""
        unsupported_data = object()

        with patch('rich.console.Console.print') as mock_print:
            OutputFormatter.format_data(unsupported_data, OutputFormat.TABLE)
            mock_print.assert_called_once()


class TestOutputFormat:
    """Test the OutputFormat enum."""

    def test_output_format_values(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.YAML.value == "yaml"
        assert OutputFormat.TEXT.value == "text"

    def test_output_format_from_string(self):
        """Test creating OutputFormat from string value."""
        assert OutputFormat("table") == OutputFormat.TABLE
        assert OutputFormat("json") == OutputFormat.JSON
        assert OutputFormat("yaml") == OutputFormat.YAML
        assert OutputFormat("text") == OutputFormat.TEXT