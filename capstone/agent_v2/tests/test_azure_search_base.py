"""
Unit tests for AzureSearchBase class.
"""

import pytest
import os
import sys
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.azure_search_base import AzureSearchBase


class TestAzureSearchBase:
    """Unit tests for AzureSearchBase class."""

    def test_missing_endpoint_raises_error(self):
        """Test that missing AZURE_SEARCH_ENDPOINT raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AzureSearchBase()

            assert "AZURE_SEARCH_ENDPOINT" in str(exc_info.value)
            assert "AZURE_SEARCH_API_KEY" in str(exc_info.value)

    def test_missing_api_key_raises_error(self):
        """Test that missing AZURE_SEARCH_API_KEY raises ValueError."""
        with patch.dict(os.environ, {"AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AzureSearchBase()

            assert "AZURE_SEARCH_API_KEY" in str(exc_info.value)

    def test_valid_config_succeeds(self):
        """Test that valid configuration initializes successfully."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            assert base.endpoint == "https://test.search.windows.net"
            assert base.api_key == "test-key"
            assert base.documents_index == "documents-metadata"  # default
            assert base.content_index == "content-blocks"  # default

    def test_custom_index_names(self):
        """Test that custom index names from env vars are used."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key",
            "AZURE_SEARCH_DOCUMENTS_INDEX": "custom-docs",
            "AZURE_SEARCH_CONTENT_INDEX": "custom-content"
        }):
            base = AzureSearchBase()
            assert base.documents_index == "custom-docs"
            assert base.content_index == "custom-content"

    def test_security_filter_with_full_context(self):
        """Test security filter generation with complete user context."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {
                "user_id": "user123",
                "department": "engineering",
                "org_id": "org456"
            }

            filter_str = base.build_security_filter(user_context)

            assert "access_control_list/any(acl:" in filter_str
            assert "acl eq 'user123'" in filter_str
            assert "acl eq 'engineering'" in filter_str
            assert "acl eq 'org456'" in filter_str
            assert " or " in filter_str

    def test_security_filter_with_partial_context(self):
        """Test security filter with only some fields present."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"user_id": "user123"}

            filter_str = base.build_security_filter(user_context)

            assert "acl eq 'user123'" in filter_str
            assert "engineering" not in filter_str

    def test_security_filter_with_none_context(self):
        """Test that None user_context returns empty filter."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            filter_str = base.build_security_filter(None)

            assert filter_str == ""

    def test_security_filter_with_empty_context(self):
        """Test that empty user_context dict returns empty filter."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            filter_str = base.build_security_filter({})

            assert filter_str == ""

    def test_get_search_client_returns_async_client(self):
        """Test that get_search_client returns AsyncSearchClient."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            client = base.get_search_client("test-index")

            from azure.search.documents.aio import SearchClient
            assert isinstance(client, SearchClient)

    def test_security_filter_with_single_quote_injection(self):
        """Test that single quotes in user context are properly escaped."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"user_id": "user' or 1=1 --"}

            # Should raise ValueError due to dangerous characters
            with pytest.raises(ValueError) as exc_info:
                base.build_security_filter(user_context)

            assert "dangerous character" in str(exc_info.value).lower()

    def test_security_filter_with_escaped_quotes(self):
        """Test that legitimate single quotes are properly escaped."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"user_id": "O'Brien"}

            filter_str = base.build_security_filter(user_context)

            # Single quote should be doubled for OData escaping
            assert "O''Brien" in filter_str
            assert "acl eq 'O''Brien'" in filter_str

    def test_security_filter_rejects_sql_comment_injection(self):
        """Test that SQL comment injection attempts are rejected."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"department": "eng--admin"}

            with pytest.raises(ValueError) as exc_info:
                base.build_security_filter(user_context)

            assert "dangerous character" in str(exc_info.value).lower()

    def test_security_filter_rejects_comment_block_injection(self):
        """Test that comment block injection attempts are rejected."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"org_id": "org/*bypass*/123"}

            with pytest.raises(ValueError) as exc_info:
                base.build_security_filter(user_context)

            assert "dangerous character" in str(exc_info.value).lower()

    def test_security_filter_rejects_non_string_values(self):
        """Test that non-string values are rejected."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"user_id": 12345}  # Integer instead of string

            with pytest.raises(ValueError) as exc_info:
                base.build_security_filter(user_context)

            assert "must be string" in str(exc_info.value).lower()

    def test_sanitize_filter_value_escapes_quotes(self):
        """Test that _sanitize_filter_value properly escapes single quotes."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()

            result = base._sanitize_filter_value("O'Neill")
            assert result == "O''Neill"

    def test_sanitize_filter_value_rejects_backslash(self):
        """Test that backslashes are rejected as potentially dangerous."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()

            with pytest.raises(ValueError):
                base._sanitize_filter_value("user\\admin")
