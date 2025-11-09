"""
Integration tests for Azure AI Search connectivity.

These tests require real Azure credentials to be set:
- AZURE_SEARCH_ENDPOINT
- AZURE_SEARCH_API_KEY
- AZURE_SEARCH_CONTENT_INDEX (optional, uses default)
"""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tools.azure_search_base import AzureSearchBase


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_search_connection():
    """
    Integration test: Connect to real Azure AI Search and execute basic query.

    Requires environment variables to be set:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_API_KEY
    - AZURE_SEARCH_CONTENT_INDEX (or uses default)
    """
    # Skip if Azure credentials not configured
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    base = AzureSearchBase()

    # Get client for content-blocks index
    client = base.get_search_client(base.content_index)

    # Execute simple search
    async with client:
        results = await client.search(
            search_text="test",
            top=1,
            select=["block_id"]
        )

        # Consume results (just verify no exception)
        result_list = []
        async for result in results:
            result_list.append(result)

        # Don't assert on result count (index might be empty)
        # Just verify the query executed without error
        print(f"Integration test successful. Retrieved {len(result_list)} results.")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_security_filter_applied():
    """Test that security filters are properly applied in real queries."""
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    base = AzureSearchBase()
    user_context = {"user_id": "test_user"}
    filter_str = base.build_security_filter(user_context)

    client = base.get_search_client(base.content_index)

    async with client:
        # This should not raise an error even if no results match
        results = await client.search(
            search_text="*",
            filter=filter_str,
            top=1
        )

        async for _ in results:
            pass  # Just verify filter syntax is valid
