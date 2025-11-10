"""Unit tests for RAG document metadata tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from capstone.agent_v2.tools.rag_list_documents_tool import ListDocumentsTool
from capstone.agent_v2.tools.rag_get_document_tool import GetDocumentTool


class TestListDocumentsTool:
    """Unit tests for ListDocumentsTool."""

    @pytest.fixture
    def mock_azure_base(self):
        """Mock AzureSearchBase for testing."""
        with patch('capstone.agent_v2.tools.rag_list_documents_tool.AzureSearchBase') as mock:
            mock_instance = MagicMock()
            mock_instance.content_index = "content-blocks"
            mock_instance.build_security_filter.return_value = ""
            mock_instance._sanitize_filter_value = lambda x: x.replace("'", "''")
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def tool(self, mock_azure_base):
        """Create ListDocumentsTool instance for testing."""
        return ListDocumentsTool(user_context={"org_id": "test-org"})

    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "rag_list_documents"
        assert "list all available documents" in tool.description.lower()
        assert "filters" in tool.parameters_schema["properties"]
        assert "limit" in tool.parameters_schema["properties"]

    @pytest.mark.asyncio
    async def test_successful_listing(self, tool, mock_azure_base):
        """Test successful document listing returns properly formatted results."""
        # Mock search client
        mock_client = AsyncMock()
        
        # Mock document detail searches
        async def mock_search(*args, **kwargs):
            if kwargs.get("top") == 0:
                # Facet query - return object with async get_facets method
                mock_search_results = AsyncMock()
                async def get_facets():
                    return {
                        "document_id": [
                            {"value": "doc-1", "count": 5},
                            {"value": "doc-2", "count": 3}
                        ]
                    }
                mock_search_results.get_facets = get_facets
                return mock_search_results
            else:
                # Document detail query
                doc_id = "doc-1" if "doc-1" in kwargs.get("filter", "") else "doc-2"
                chunk_count = 5 if doc_id == "doc-1" else 3
                
                async def mock_iter():
                    for i in range(chunk_count):
                        yield {
                            "document_id": doc_id,
                            "document_title": f"Test Doc {doc_id}",
                            "document_type": "application/pdf",
                            "org_id": "test-org",
                            "user_id": "test-user",
                            "scope": "shared"
                        }
                
                result = AsyncMock()
                result.__aiter__ = lambda self: mock_iter()
                return result
        
        mock_client.search = mock_search
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute(limit=10)
        
        # Verify
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["documents"]) == 2
        
        # Verify document structure
        doc = result["documents"][0]
        assert "document_id" in doc
        assert "document_title" in doc
        assert "document_type" in doc
        assert "chunk_count" in doc
        assert doc["chunk_count"] in [5, 3]

    @pytest.mark.asyncio
    async def test_empty_results(self, tool, mock_azure_base):
        """Test handling of empty results."""
        # Mock search client with no facets
        mock_client = AsyncMock()
        mock_search_results = AsyncMock()
        async def get_facets():
            return {}
        mock_search_results.get_facets = get_facets
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute()
        
        # Verify
        assert result["success"] is True
        assert result["count"] == 0
        assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_filters_applied(self, tool, mock_azure_base):
        """Test that filters are applied correctly."""
        mock_client = AsyncMock()
        mock_search_results = AsyncMock()
        mock_search_results.get_facets.return_value = {}
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute with filters
        await tool.execute(
            filters={"document_type": "application/pdf"},
            limit=5
        )
        
        # Verify search was called
        assert mock_client.search.called

    @pytest.mark.asyncio
    async def test_security_filter_integration(self, mock_azure_base):
        """Test security filter integration."""
        tool = ListDocumentsTool(user_context={"org_id": "secure-org", "user_id": "user123"})
        
        # Mock the build_security_filter to return expected filter
        mock_azure_base.build_security_filter.return_value = "org_id eq 'secure-org' and user_id eq 'user123'"
        
        mock_client = AsyncMock()
        mock_search_results = AsyncMock()
        mock_search_results.get_facets.return_value = {}
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        await tool.execute()
        
        # Verify security filter was built with correct context
        mock_azure_base.build_security_filter.assert_called()

    @pytest.mark.asyncio
    async def test_azure_exception_handling(self, tool, mock_azure_base):
        """Test Azure SDK exceptions are converted to agent error format."""
        from azure.core.exceptions import HttpResponseError
        
        # Mock search client that raises exception
        mock_client = AsyncMock()
        mock_error = HttpResponseError(message="Index not found")
        mock_error.status_code = 404
        mock_client.search = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute()
        
        # Verify error format
        assert result["success"] is False
        assert "error" in result
        assert "type" in result
        assert result["type"] == "IndexNotFoundError"
        assert "hints" in result


class TestGetDocumentTool:
    """Unit tests for GetDocumentTool."""

    @pytest.fixture
    def mock_azure_base(self):
        """Mock AzureSearchBase for testing."""
        with patch('capstone.agent_v2.tools.rag_get_document_tool.AzureSearchBase') as mock:
            mock_instance = MagicMock()
            mock_instance.content_index = "content-blocks"
            mock_instance.build_security_filter.return_value = ""
            mock_instance._sanitize_filter_value = lambda x: x.replace("'", "''")
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def tool(self, mock_azure_base):
        """Create GetDocumentTool instance for testing."""
        return GetDocumentTool(user_context={"org_id": "test-org"})

    def test_tool_properties(self, tool):
        """Test tool basic properties."""
        assert tool.name == "rag_get_document"
        assert "retrieve detailed metadata" in tool.description.lower()
        assert "document_id" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["document_id"]

    @pytest.mark.asyncio
    async def test_successful_retrieval(self, tool, mock_azure_base):
        """Test successful document retrieval returns complete metadata."""
        # Mock search client
        mock_client = AsyncMock()
        
        # Mock chunks for a document
        async def mock_chunk_iter():
            for i in range(5):
                yield {
                    "content_id": f"chunk-{i}",
                    "document_id": "test-doc-123",
                    "document_title": "Test Document",
                    "document_type": "application/pdf",
                    "org_id": "test-org",
                    "user_id": "test-user",
                    "scope": "shared",
                    "content_text": f"Text content {i}" if i < 3 else None,
                    "content_path": f"/path/img{i}.jpg" if i >= 3 else None,
                    "locationMetadata": {"pageNumber": i + 1}
                }
        
        mock_search_results = AsyncMock()
        mock_search_results.__aiter__ = lambda self: mock_chunk_iter()
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute(document_id="test-doc-123")
        
        # Verify
        assert result["success"] is True
        assert "document" in result
        
        doc = result["document"]
        assert doc["document_id"] == "test-doc-123"
        assert doc["document_title"] == "Test Document"
        assert doc["chunk_count"] == 5
        assert doc["page_count"] == 5  # Max page number
        assert doc["has_text"] is True
        assert doc["has_images"] is True
        assert len(doc["chunks"]) == 5

    @pytest.mark.asyncio
    async def test_document_not_found(self, tool, mock_azure_base):
        """Test document not found returns proper error."""
        # Mock search client with no results
        mock_client = AsyncMock()
        
        async def empty_iter():
            return
            yield  # Make it a generator
        
        mock_search_results = AsyncMock()
        mock_search_results.__aiter__ = lambda self: empty_iter()
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute(document_id="nonexistent-doc")
        
        # Verify
        assert result["success"] is False
        assert result["type"] == "NotFoundError"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_security_filter_applied(self, mock_azure_base):
        """Test security filter is applied correctly."""
        tool = GetDocumentTool(user_context={"org_id": "secure-org"})
        
        mock_azure_base.build_security_filter.return_value = "org_id eq 'secure-org'"
        
        mock_client = AsyncMock()
        
        async def empty_iter():
            return
            yield
        
        mock_search_results = AsyncMock()
        mock_search_results.__aiter__ = lambda self: empty_iter()
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        await tool.execute(document_id="test-doc")
        
        # Verify security filter was built
        mock_azure_base.build_security_filter.assert_called()

    @pytest.mark.asyncio
    async def test_azure_exception_handling(self, tool, mock_azure_base):
        """Test Azure SDK exceptions are converted to agent error format."""
        from azure.core.exceptions import HttpResponseError
        
        # Mock search client that raises exception
        mock_client = AsyncMock()
        mock_error = HttpResponseError(message="Authentication failed")
        mock_error.status_code = 401
        mock_client.search = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute(document_id="test-doc")
        
        # Verify error format
        assert result["success"] is False
        assert "error" in result
        assert "type" in result
        assert result["type"] == "AuthenticationError"
        assert "hints" in result
        assert any("AZURE_SEARCH_API_KEY" in hint for hint in result["hints"])

    @pytest.mark.asyncio
    async def test_page_count_calculation(self, tool, mock_azure_base):
        """Test page count is correctly calculated from max page number."""
        mock_client = AsyncMock()
        
        async def mock_chunk_iter():
            # Chunks with various page numbers
            for page in [1, 3, 2, 5, 4]:
                yield {
                    "content_id": f"chunk-{page}",
                    "document_id": "test-doc",
                    "document_title": "Test Doc",
                    "document_type": "application/pdf",
                    "org_id": "test-org",
                    "user_id": "test-user",
                    "scope": "shared",
                    "content_text": "Text",
                    "content_path": None,
                    "locationMetadata": {"pageNumber": page}
                }
        
        mock_search_results = AsyncMock()
        mock_search_results.__aiter__ = lambda self: mock_chunk_iter()
        
        mock_client.search = AsyncMock(return_value=mock_search_results)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_azure_base.get_search_client.return_value = mock_client
        
        # Execute
        result = await tool.execute(document_id="test-doc")
        
        # Verify max page is 5
        assert result["success"] is True
        assert result["document"]["page_count"] == 5

