"""Integration tests for RAG document metadata tools with real Azure AI Search."""

import os
import pytest
from capstone.agent_v2.tools.rag_list_documents_tool import ListDocumentsTool
from capstone.agent_v2.tools.rag_get_document_tool import GetDocumentTool
from capstone.agent_v2.agent import Agent


# Skip tests if Azure credentials are not available
pytestmark = pytest.mark.skipif(
    not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"),
    reason="Azure Search credentials not configured"
)


class TestListDocumentsToolIntegration:
    """Integration tests for ListDocumentsTool with real Azure AI Search."""

    @pytest.fixture
    def tool(self):
        """Create ListDocumentsTool instance for integration testing."""
        # Use real Azure credentials from environment
        return ListDocumentsTool(user_context={
            "org_id": "MS-corp",
            "user_id": "ms-user",
            "scope": "shared"
        })

    @pytest.mark.asyncio
    async def test_list_documents_from_real_index(self, tool):
        """Test listing documents from real content-blocks index using facets."""
        result = await tool.execute(limit=10)
        
        # Verify successful response
        assert result["success"] is True
        assert "documents" in result
        assert "count" in result
        assert isinstance(result["documents"], list)
        assert result["count"] == len(result["documents"])
        
        # If documents exist, verify structure
        if result["count"] > 0:
            doc = result["documents"][0]
            assert "document_id" in doc
            assert "document_title" in doc
            assert "document_type" in doc
            assert "org_id" in doc
            assert "user_id" in doc
            assert "scope" in doc
            assert "chunk_count" in doc
            assert isinstance(doc["chunk_count"], int)
            assert doc["chunk_count"] > 0

    @pytest.mark.asyncio
    async def test_list_documents_with_filters(self, tool):
        """Test listing documents with additional filters."""
        result = await tool.execute(
            filters={"document_type": "application/pdf"},
            limit=5
        )
        
        assert result["success"] is True
        assert result["count"] <= 5
        
        # Verify all returned documents match filter
        for doc in result["documents"]:
            assert doc["document_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_list_documents_respects_limit(self, tool):
        """Test that limit parameter is respected."""
        result = await tool.execute(limit=3)
        
        assert result["success"] is True
        assert result["count"] <= 3
        assert len(result["documents"]) <= 3

    @pytest.mark.asyncio
    async def test_security_filter_works(self):
        """Test security filters work correctly with org_id/user_id/scope."""
        # Tool with specific user context
        tool = ListDocumentsTool(user_context={
            "org_id": "MS-corp",
            "user_id": "ms-user"
        })
        
        result = await tool.execute()
        
        assert result["success"] is True
        
        # Verify all documents match security context
        for doc in result["documents"]:
            assert doc["org_id"] == "MS-corp"
            # Document should be owned by user or shared
            assert doc["user_id"] == "ms-user" or doc.get("scope") in ["shared", "public"]

    @pytest.mark.asyncio
    async def test_faceting_returns_unique_documents(self, tool):
        """Test that faceting returns distinct document_id values."""
        result = await tool.execute(limit=20)
        
        assert result["success"] is True
        
        # Verify all document IDs are unique
        doc_ids = [doc["document_id"] for doc in result["documents"]]
        assert len(doc_ids) == len(set(doc_ids)), "Duplicate document IDs found"


class TestGetDocumentToolIntegration:
    """Integration tests for GetDocumentTool with real Azure AI Search."""

    @pytest.fixture
    def tool(self):
        """Create GetDocumentTool instance for integration testing."""
        return GetDocumentTool(user_context={
            "org_id": "MS-corp",
            "user_id": "ms-user",
            "scope": "shared"
        })

    @pytest.fixture
    def sample_document_id(self):
        """Get a sample document ID from the index for testing."""
        # Return a well-known test document ID
        # In real tests with Azure, this would be a known document in the test index
        return "test-doc-id-placeholder"

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, tool, sample_document_id):
        """Test retrieving specific document by document_id."""
        result = await tool.execute(document_id=sample_document_id)
        
        assert result["success"] is True
        assert "document" in result
        
        doc = result["document"]
        assert doc["document_id"] == sample_document_id
        assert "document_title" in doc
        assert "document_type" in doc
        assert "chunk_count" in doc
        assert "has_images" in doc
        assert "has_text" in doc
        assert "chunks" in doc
        assert isinstance(doc["chunk_count"], int)
        assert doc["chunk_count"] > 0
        assert len(doc["chunks"]) == doc["chunk_count"]

    @pytest.mark.asyncio
    async def test_get_document_calculates_page_count(self, tool, sample_document_id):
        """Test that page_count is correctly calculated from locationMetadata."""
        result = await tool.execute(document_id=sample_document_id)
        
        assert result["success"] is True
        doc = result["document"]
        
        # If document has pages, verify page_count exists
        if doc.get("page_count") is not None:
            assert isinstance(doc["page_count"], int)
            assert doc["page_count"] > 0

    @pytest.mark.asyncio
    async def test_get_document_detects_content_types(self, tool, sample_document_id):
        """Test that has_images and has_text flags are correctly set."""
        result = await tool.execute(document_id=sample_document_id)
        
        assert result["success"] is True
        doc = result["document"]
        
        # At least one content type should be present
        assert doc["has_text"] or doc["has_images"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, tool):
        """Test retrieving nonexistent document returns NotFoundError."""
        result = await tool.execute(document_id="00000000-0000-0000-0000-000000000000")
        
        assert result["success"] is False
        assert result["type"] == "NotFoundError"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_security_filter_applied(self):
        """Test security filters are applied correctly."""
        # Create tool with specific security context
        tool = GetDocumentTool(user_context={
            "org_id": "MS-corp",
            "user_id": "ms-user"
        })
        
        # First get a valid document ID
        list_tool = ListDocumentsTool(user_context={
            "org_id": "MS-corp",
            "user_id": "ms-user"
        })
        list_result = await list_tool.execute(limit=1)
        
        if list_result["count"] == 0:
            pytest.skip("No documents available for testing")
        
        doc_id = list_result["documents"][0]["document_id"]
        
        # Get the document
        result = await tool.execute(document_id=doc_id)
        
        assert result["success"] is True
        doc = result["document"]
        
        # Verify document matches security context
        assert doc["org_id"] == "MS-corp"


class TestRagDocumentToolsWithAgent:
    """Integration tests for document tools with agent instance."""

    @pytest.fixture
    def agent(self):
        """Create RAG agent with document tools."""
        return Agent.create_rag_agent(
            session_id="test_doc_tools_session",
            user_context={
                "org_id": "MS-corp",
                "user_id": "ms-user",
                "scope": "shared"
            }
        )

    @pytest.mark.asyncio
    async def test_agent_has_document_tools(self, agent):
        """Test that RAG agent includes document metadata tools."""
        tool_names = [tool.name for tool in agent.tools]
        
        assert "rag_list_documents" in tool_names
        assert "rag_get_document" in tool_names
        assert "rag_semantic_search" in tool_names

    @pytest.mark.asyncio
    async def test_document_tools_work_with_agent(self, agent):
        """Test that document tools can be called through agent."""
        # Get list documents tool
        list_tool = next(
            tool for tool in agent.tools 
            if tool.name == "rag_list_documents"
        )
        
        # Execute through tool
        result = await list_tool.execute(limit=5)
        
        assert result["success"] is True
        assert "documents" in result

    @pytest.mark.asyncio
    async def test_tools_use_agent_user_context(self, agent):
        """Test that tools use user context from agent creation."""
        list_tool = next(
            tool for tool in agent.tools 
            if tool.name == "rag_list_documents"
        )
        
        # Verify tool has correct user context
        assert list_tool.user_context["org_id"] == "MS-corp"
        assert list_tool.user_context["user_id"] == "ms-user"

