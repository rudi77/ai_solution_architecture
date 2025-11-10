"""
Azure AI Search Base Infrastructure

Provides shared connection and security infrastructure for all RAG tools
that integrate with Azure AI Search.
"""

import os
from typing import Any, Dict, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient


class AzureSearchBase:
    """Base class for Azure AI Search integration providing shared connection and security logic."""

    def __init__(self):
        """Initialize Azure Search base configuration from environment variables."""
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.api_key = os.getenv("AZURE_SEARCH_API_KEY")
        self.documents_index = os.getenv("AZURE_SEARCH_DOCUMENTS_INDEX", "documents-metadata")
        self.content_index = os.getenv("AZURE_SEARCH_CONTENT_INDEX", "content-blocks")

        # Validate required environment variables
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure Search configuration missing. Please set:\n"
                "  AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net\n"
                "  AZURE_SEARCH_API_KEY=your-api-key\n"
                "Optional:\n"
                "  AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata (default)\n"
                "  AZURE_SEARCH_CONTENT_INDEX=content-blocks (default)"
            )

    def get_search_client(self, index_name: str) -> SearchClient:
        """
        Create an AsyncSearchClient for the specified index.

        Args:
            index_name: Name of the Azure Search index

        Returns:
            AsyncSearchClient configured with credentials

        Example:
            client = self.get_search_client("content-blocks")
            async with client:
                results = await client.search(...)
        """
        return SearchClient(
            endpoint=self.endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(self.api_key)
        )

    def build_security_filter(self, user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build OData filter for row-level security based on user context.

        Implements proper access control logic:
        - Documents must belong to the organization (org_id match)
        - Documents are accessible if:
          - They belong to the user (user_id match), OR
          - They are shared/public (scope eq 'shared' or 'public')

        Args:
            user_context: Dict with user_id, org_id, scope keys

        Returns:
            OData filter string for access control

        Examples:
            >>> build_security_filter({"user_id": "ms-user", "org_id": "MS-corp"})
            "org_id eq 'MS-corp' and user_id eq 'ms-user'"

            >>> build_security_filter({"user_id": "ms-user", "org_id": "MS-corp", "scope": "shared"})
            "org_id eq 'MS-corp' and (user_id eq 'ms-user' or scope eq 'shared')"

            >>> build_security_filter({"org_id": "MS-corp"})
            "org_id eq 'MS-corp'"

            >>> build_security_filter(None)
            ""

        Raises:
            ValueError: If user context values contain invalid characters
        """
        if not user_context:
            return ""  # No filter for testing scenarios

        filters = []
        
        # Organization filter (required if provided)
        org_id = user_context.get("org_id")
        if org_id:
            sanitized_org = self._sanitize_filter_value(org_id)
            filters.append(f"org_id eq '{sanitized_org}'")
        
        # User/Scope access filter (OR logic)
        user_id = user_context.get("user_id")
        scope = user_context.get("scope")
        
        access_filters = []
        if user_id:
            sanitized_user = self._sanitize_filter_value(user_id)
            access_filters.append(f"user_id eq '{sanitized_user}'")
        if scope:
            sanitized_scope = self._sanitize_filter_value(scope)
            access_filters.append(f"scope eq '{sanitized_scope}'")
        
        # Combine access filters with OR
        if access_filters:
            if len(access_filters) == 1:
                filters.append(access_filters[0])
            else:
                filters.append(f"({' or '.join(access_filters)})")
        
        if not filters:
            return ""

        # Combine all filters with AND
        return " and ".join(filters)

    def _sanitize_filter_value(self, value: str) -> str:
        """
        Sanitize a value for use in OData filter expressions.

        Prevents OData injection by escaping single quotes and validating format.

        Args:
            value: The value to sanitize

        Returns:
            Sanitized value safe for use in OData filters

        Raises:
            ValueError: If value contains potentially malicious characters
        """
        if not isinstance(value, str):
            raise ValueError(f"Filter value must be string, got {type(value)}")

        # Check for suspicious patterns that could indicate injection attempts
        dangerous_chars = [";", "--", "/*", "*/", "\\"]
        for char in dangerous_chars:
            if char in value:
                raise ValueError(
                    f"Filter value contains potentially dangerous character sequence: {char}"
                )

        # Escape single quotes by doubling them (OData standard)
        sanitized = value.replace("'", "''")

        return sanitized

    async def __aenter__(self):
        """Support async context manager pattern."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on context exit."""
        # No cleanup needed for SearchClient (handled per-use)
        pass
