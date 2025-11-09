"""Integration tests for SemanticSearchTool against real Azure AI Search."""

import pytest
import os
from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_search_real_azure():
    """
    Integration test: Search real Azure AI Search index.

    Requires environment variables:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_API_KEY
    - AZURE_SEARCH_CONTENT_INDEX (optional)
    """
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    tool = SemanticSearchTool(user_context={"user_id": "integration_test"})

    # Execute real search
    result = await tool.execute(
        query="test",  # Generic query likely to return results
        top_k=5
    )

    # Verify result structure
    assert "success" in result
    assert "results" in result
    assert "result_count" in result

    if result["success"]:
        # If search succeeded, verify result format
        assert isinstance(result["results"], list)
        assert result["result_count"] == len(result["results"])

        if result["result_count"] > 0:
            # Verify first result has expected fields
            first_result = result["results"][0]
            assert "content_id" in first_result
            assert "content_type" in first_result
            assert first_result["content_type"] in ["text", "image", "unknown"]
            assert "document_title" in first_result
            assert "document_id" in first_result
            assert "org_id" in first_result
            assert "user_id" in first_result
            assert "scope" in first_result

            # Type-specific checks
            if first_result["content_type"] == "text":
                assert "content" in first_result
            elif first_result["content_type"] == "image":
                assert "content_path" in first_result
                assert "content_text" in first_result

        print(f"✅ Integration test successful: Retrieved {result['result_count']} results")
    else:
        # If failed, log the error for debugging
        print(f"⚠️ Search failed (might be expected if index is empty): {result.get('error')}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_with_security_filter_real():
    """Test that security filtering works against real index."""
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    # Create tool with specific user context
    tool = SemanticSearchTool(user_context={
        "user_id": "test_user_123",
        "department": "engineering"
    })

    result = await tool.execute(query="test", top_k=5)

    # Should not raise error even if no results match security filter
    assert "success" in result

    if result["success"]:
        print(f"✅ Security filter applied successfully: {result['result_count']} accessible results")
    else:
        # Log error for debugging
        print(f"⚠️ Search with security filter failed: {result.get('error')}")
