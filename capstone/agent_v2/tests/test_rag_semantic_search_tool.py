"""Unit tests for SemanticSearchTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool


@pytest.fixture
def mock_azure_base():
    """Mock AzureSearchBase for testing."""
    with patch("capstone.agent_v2.tools.rag_semantic_search_tool.AzureSearchBase") as mock:
        instance = mock.return_value
        instance.endpoint = "https://test.search.windows.net"
        instance.content_index = "content-blocks"
        instance.build_security_filter.return_value = ""
        yield instance


@pytest.fixture
def search_tool(mock_azure_base):
    """Create SemanticSearchTool instance for testing."""
    return SemanticSearchTool(user_context={"user_id": "test_user"})


class TestSemanticSearchTool:
    """Test suite for SemanticSearchTool."""

    def test_tool_properties(self, search_tool):
        """Test that tool properties are correctly defined."""
        assert search_tool.name == "rag_semantic_search"
        assert "multimodal" in search_tool.description.lower()
        assert "query" in search_tool.parameters_schema["properties"]
        assert search_tool.parameters_schema["required"] == ["query"]

    def test_parameters_schema_structure(self, search_tool):
        """Test parameter schema has correct structure."""
        schema = search_tool.parameters_schema

        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["top_k"]["type"] == "integer"
        assert schema["properties"]["top_k"]["default"] == 10
        assert schema["properties"]["top_k"]["maximum"] == 50

    @pytest.mark.asyncio
    async def test_successful_search_with_text_results(self, search_tool, mock_azure_base):
        """Test successful search returning text blocks."""
        # Mock search client and results
        mock_client = AsyncMock()
        mock_results = [
            {
                "content_id": "text_chunk_1",
                "text_document_id": "doc1_text",
                "image_document_id": None,
                "content_text": "Test content about pumps",
                "document_id": "doc1",
                "document_title": "manual.pdf",
                "document_type": "application/pdf",
                "locationMetadata": {"pageNumber": 5},
                "org_id": "MS-corp",
                "user_id": "ms-user",
                "scope": "shared",
                "@search.score": 0.95
            },
            {
                "content_id": "text_chunk_2",
                "text_document_id": "doc1_text",
                "image_document_id": None,
                "content_text": "More information",
                "document_id": "doc1",
                "document_title": "manual.pdf",
                "document_type": "application/pdf",
                "locationMetadata": {"pageNumber": 6},
                "org_id": "MS-corp",
                "user_id": "ms-user",
                "scope": "shared",
                "@search.score": 0.85
            }
        ]

        # Setup async iteration
        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter(mock_results))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        # Execute search
        result = await search_tool.execute(query="How does the pump work?", top_k=2)

        # Verify results
        assert result["success"] is True
        assert result["result_count"] == 2
        assert len(result["results"]) == 2

        # Verify first result structure
        first_result = result["results"][0]
        assert first_result["content_type"] == "text"
        assert first_result["content"] == "Test content about pumps"
        assert first_result["document_title"] == "manual.pdf"
        assert first_result["page_number"] == 5
        assert first_result["score"] == 0.95
        assert first_result["org_id"] == "MS-corp"
        assert first_result["user_id"] == "ms-user"
        assert first_result["scope"] == "shared"

    @pytest.mark.asyncio
    async def test_successful_search_with_image_results(self, search_tool, mock_azure_base):
        """Test successful search returning image blocks."""
        mock_client = AsyncMock()
        mock_results = [
            {
                "content_id": "img_chunk_1",
                "text_document_id": None,
                "image_document_id": "doc1_img",
                "content_text": "Diagram of XYZ pump",
                "content_path": "bluchat-images-test/doc1/image1.jpg",
                "document_id": "doc1",
                "document_title": "manual.pdf",
                "document_type": "application/pdf",
                "locationMetadata": {"pageNumber": 7},
                "org_id": "MS-corp",
                "user_id": "ms-user",
                "scope": "shared",
                "@search.score": 0.90
            }
        ]

        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter(mock_results))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        result = await search_tool.execute(query="pump diagram", top_k=1)

        assert result["success"] is True
        assert result["result_count"] == 1

        image_result = result["results"][0]
        assert image_result["content_type"] == "image"
        assert image_result["content_path"] == "bluchat-images-test/doc1/image1.jpg"
        assert image_result["content_text"] == "Diagram of XYZ pump"
        assert "content" not in image_result  # Images don't have content field (only content_text for description)

    @pytest.mark.asyncio
    async def test_empty_results(self, search_tool, mock_azure_base):
        """Test that empty results are handled correctly (not an error)."""
        mock_client = AsyncMock()

        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        result = await search_tool.execute(query="nonexistent query", top_k=10)

        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_security_filter_applied(self, search_tool, mock_azure_base):
        """Test that security filter is correctly applied."""
        mock_azure_base.build_security_filter.return_value = "user_id eq 'test_user'"

        mock_client = AsyncMock()
        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        await search_tool.execute(query="test", top_k=5)

        # Verify security filter was built with user context
        mock_azure_base.build_security_filter.assert_called_once_with({"user_id": "test_user"})

        # Verify search was called with filter
        call_args = mock_client.search.call_args
        assert "filter" in call_args.kwargs
        # Filter should contain security filter
        assert call_args.kwargs["filter"] is not None

    @pytest.mark.asyncio
    async def test_additional_filters_combined(self, search_tool, mock_azure_base):
        """Test that additional filters are combined with security filter."""
        mock_azure_base.build_security_filter.return_value = "user_id eq 'test_user'"

        mock_client = AsyncMock()
        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        # Execute with additional filters
        await search_tool.execute(
            query="test",
            top_k=5,
            filters={"document_type": "Manual"}
        )

        # Verify filter contains both security and additional filters
        call_args = mock_client.search.call_args
        filter_str = call_args.kwargs["filter"]
        assert "user_id" in filter_str
        assert "document_type eq 'Manual'" in filter_str

    @pytest.mark.asyncio
    async def test_top_k_validation(self, search_tool, mock_azure_base):
        """Test that top_k is validated and clamped."""
        mock_client = AsyncMock()
        async def async_iter(items):
            for item in items:
                yield item

        mock_client.search = AsyncMock(return_value=async_iter([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        # Test too large
        await search_tool.execute(query="test", top_k=100)
        assert mock_client.search.call_args.kwargs["top"] == 50  # Clamped to max

        # Test too small
        await search_tool.execute(query="test", top_k=-5)
        assert mock_client.search.call_args.kwargs["top"] == 1  # Clamped to min

    @pytest.mark.asyncio
    async def test_http_error_handling(self, search_tool, mock_azure_base):
        """Test handling of Azure HTTP errors."""
        from azure.core.exceptions import HttpResponseError

        mock_client = AsyncMock()
        mock_client.search.side_effect = HttpResponseError(
            message="Index not found",
            response=MagicMock(status_code=404)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        result = await search_tool.execute(query="test", top_k=5)

        assert result["success"] is False
        assert result["type"] == "IndexNotFoundError"
        assert "404" in result["error"]
        assert len(result["hints"]) > 0
        assert "content-blocks" in result["hints"][0]

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, search_tool, mock_azure_base):
        """Test handling of authentication errors."""
        from azure.core.exceptions import HttpResponseError

        mock_client = AsyncMock()
        mock_client.search.side_effect = HttpResponseError(
            message="Authentication failed",
            response=MagicMock(status_code=401)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        result = await search_tool.execute(query="test", top_k=5)

        assert result["success"] is False
        assert result["type"] == "AuthenticationError"
        assert "AZURE_SEARCH_API_KEY" in result["hints"][0]

    @pytest.mark.asyncio
    async def test_network_error_handling(self, search_tool, mock_azure_base):
        """Test handling of network errors."""
        from azure.core.exceptions import ServiceRequestError

        mock_client = AsyncMock()
        mock_client.search.side_effect = ServiceRequestError("Connection timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_azure_base.get_search_client.return_value = mock_client

        result = await search_tool.execute(query="test", top_k=5)

        assert result["success"] is False
        assert result["type"] == "NetworkError"
        assert "network connectivity" in result["hints"][0].lower()
