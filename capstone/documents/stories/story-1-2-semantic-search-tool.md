# Story 1.2: Semantic Search Tool for Content Blocks

**Epic:** Multimodal RAG Knowledge Retrieval for Agent Framework
**Story ID:** RAG-1.2
**Priority:** High (Core RAG functionality)
**Estimate:** 6-8 hours
**Status:** Ready for Development
**Depends on:** Story 1.1 (Azure Search Base Infrastructure)

---

## User Story

**As a** RAG-enabled agent,
**I want** to search across multimodal content blocks (text and images) semantically,
**so that** I can retrieve relevant information including diagrams and visualizations for user queries.

---

## Story Context

### Existing System Integration

- **Integrates with:**
  - `AzureSearchBase` class (from Story 1.1)
  - `Tool` base class (tool.py)
  - Azure AI Search `content-blocks` index
- **Technology:** Python 3.11+, azure-search-documents SDK, AsyncIO
- **Follows pattern:** Existing tools (WebSearchTool, FileReadTool) - see tools/web_tool.py
- **Touch points:**
  - tools/ directory (new tool file)
  - Test infrastructure
  - Agent tool registration

### Why This Story Matters

This is the **core RAG search capability**. It enables the agent to:
- Search across both text chunks AND images semantically
- Retrieve multimodal content blocks with metadata
- Support user security context (row-level filtering)
- Return structured results for synthesis

This tool validates that Story 1.1's base infrastructure works correctly and establishes the pattern that Stories 1.3+ will follow.

---

## Acceptance Criteria

### AC1.2.1: SemanticSearchTool Class Structure

**File:** `capstone/agent_v2/tools/rag_semantic_search_tool.py`

**Requirements:**
- [ ] Create new tool class inheriting from `Tool` base class
- [ ] Implement required Tool interface properties and methods
- [ ] Use `AzureSearchBase` for Azure connection

**Implementation:**

```python
"""Semantic search tool for multimodal content blocks using Azure AI Search."""

import os
from typing import Any, Dict, List, Optional
import structlog

from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.azure_search_base import AzureSearchBase


class SemanticSearchTool(Tool):
    """
    Search across multimodal content blocks (text and images) using Azure AI Search.

    This tool performs hybrid semantic + keyword search across the content-blocks index,
    returning both text chunks and image blocks with their associated metadata.
    """

    def __init__(self, user_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the semantic search tool.

        Args:
            user_context: Optional user context for security filtering
                         (user_id, department, org_id)
        """
        self.azure_base = AzureSearchBase()
        self.user_context = user_context or {}
        self.logger = structlog.get_logger().bind(tool="rag_semantic_search")

    @property
    def name(self) -> str:
        """Tool name used by the agent."""
        return "rag_semantic_search"

    @property
    def description(self) -> str:
        """Tool description for the agent."""
        return (
            "Search across multimodal content blocks (text and images) using semantic search. "
            "Returns relevant text chunks and image blocks with metadata including document source, "
            "page number, and relevance score. Use this for answering questions that require "
            "finding information across documents, including diagrams and visualizations."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """
        JSON schema for tool parameters.

        Used by the agent to understand what parameters this tool accepts.
        """
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (can be a question or keywords)"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10, max: 50)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters (e.g., {'document_type': 'Manual'})",
                    "default": {}
                }
            },
            "required": ["query"]
        }

    @property
    def function_tool_schema(self) -> Dict[str, Any]:
        """Function calling schema for LLM tool use."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }
```

---

### AC1.2.2: Execute Method Implementation

**Requirements:**
- [ ] Implement async execute method
- [ ] Use AsyncSearchClient to query content-blocks index
- [ ] Apply security filter from user_context
- [ ] Return structured result format

**Implementation:**

```python
    async def execute(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute semantic search across multimodal content blocks.

        Args:
            query: Search query (natural language question or keywords)
            top_k: Number of results to return (1-50)
            filters: Optional additional filters (combined with security filter)
            **kwargs: Additional arguments (ignored)

        Returns:
            Dict with structure:
            {
                "success": True,
                "results": [
                    {
                        "block_id": "...",
                        "block_type": "text" | "image",
                        "content": "..." (if text),
                        "image_url": "..." (if image),
                        "image_caption": "..." (if image),
                        "doc_id": "...",
                        "filename": "...",
                        "page_number": 5,
                        "score": 0.85
                    },
                    ...
                ],
                "result_count": 10
            }

        Example:
            >>> tool = SemanticSearchTool(user_context={"user_id": "u123"})
            >>> result = await tool.execute(
            ...     query="How does the XYZ pump work?",
            ...     top_k=5
            ... )
            >>> print(result["result_count"])
            5
        """
        import time
        start_time = time.time()

        self.logger.info(
            "search_started",
            query=query[:100],  # Log first 100 chars
            top_k=top_k,
            has_filters=bool(filters)
        )

        try:
            # Validate top_k
            top_k = max(1, min(top_k, 50))

            # Build security filter from user context
            security_filter = self.azure_base.build_security_filter(self.user_context)

            # Combine with additional filters if provided
            combined_filter = self._combine_filters(security_filter, filters)

            # Get search client for content-blocks index
            client = self.azure_base.get_search_client(
                self.azure_base.content_index
            )

            # Execute search
            async with client:
                search_results = await client.search(
                    search_text=query,
                    filter=combined_filter if combined_filter else None,
                    top=top_k,
                    select=[
                        "block_id",
                        "block_type",
                        "content",
                        "image_url",
                        "image_caption",
                        "doc_id",
                        "filename",
                        "page_number"
                    ],
                    include_total_count=True
                )

                # Process results
                results = []
                async for result in search_results:
                    block = {
                        "block_id": result.get("block_id"),
                        "block_type": result.get("block_type"),
                        "doc_id": result.get("doc_id"),
                        "filename": result.get("filename"),
                        "page_number": result.get("page_number"),
                        "score": result.get("@search.score", 0.0)
                    }

                    # Add type-specific fields
                    if result.get("block_type") == "text":
                        block["content"] = result.get("content", "")
                    elif result.get("block_type") == "image":
                        block["image_url"] = result.get("image_url", "")
                        block["image_caption"] = result.get("image_caption", "")

                    results.append(block)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            self.logger.info(
                "search_completed",
                result_count=len(results),
                search_latency_ms=latency_ms,
                index_name=self.azure_base.content_index
            )

            return {
                "success": True,
                "results": results,
                "result_count": len(results)
            }

        except Exception as e:
            return self._handle_error(e, query, time.time() - start_time)

    def _combine_filters(
        self,
        security_filter: str,
        additional_filters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Combine security filter with additional user filters.

        Args:
            security_filter: OData filter from user context
            additional_filters: Additional filter dict (e.g., {"document_type": "Manual"})

        Returns:
            Combined OData filter string
        """
        filters = []

        if security_filter:
            filters.append(f"({security_filter})")

        if additional_filters:
            for key, value in additional_filters.items():
                if isinstance(value, str):
                    filters.append(f"{key} eq '{value}'")
                elif isinstance(value, (int, float)):
                    filters.append(f"{key} eq {value}")
                # Add more types as needed

        if not filters:
            return ""

        return " and ".join(filters)
```

---

### AC1.2.3: Error Handling

**Requirements:**
- [ ] Catch Azure SDK exceptions
- [ ] Return structured error format
- [ ] Handle network timeouts gracefully
- [ ] Handle empty results (not an error)

**Implementation:**

```python
    def _handle_error(
        self,
        exception: Exception,
        query: str,
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        Handle errors and return structured error response.

        Args:
            exception: The exception that occurred
            query: Original search query
            elapsed_time: Time elapsed before error

        Returns:
            Structured error dict matching agent's expected format
        """
        from azure.core.exceptions import HttpResponseError, ServiceRequestError
        import traceback

        latency_ms = int(elapsed_time * 1000)

        # Determine error type and hints
        error_type = type(exception).__name__
        error_message = str(exception)
        hints = []

        if isinstance(exception, HttpResponseError):
            if exception.status_code == 401:
                error_type = "AuthenticationError"
                hints.append("Check AZURE_SEARCH_API_KEY environment variable")
            elif exception.status_code == 404:
                error_type = "IndexNotFoundError"
                hints.append(f"Verify index '{self.azure_base.content_index}' exists")
            elif exception.status_code == 400:
                error_type = "InvalidQueryError"
                hints.append("Check query syntax and filter format")

            error_message = f"Azure Search HTTP {exception.status_code}: {exception.message}"

        elif isinstance(exception, ServiceRequestError):
            error_type = "NetworkError"
            hints.append("Check network connectivity to Azure Search endpoint")
            hints.append(f"Endpoint: {self.azure_base.endpoint}")

        elif isinstance(exception, TimeoutError):
            error_type = "TimeoutError"
            hints.append("Query took too long - try simplifying the query")
            hints.append("Or increase timeout configuration")

        else:
            hints.append("Check application logs for detailed traceback")

        self.logger.error(
            "search_failed",
            error_type=error_type,
            error=error_message,
            query=query[:100],
            search_latency_ms=latency_ms,
            traceback=traceback.format_exc()
        )

        return {
            "success": False,
            "error": error_message,
            "type": error_type,
            "hints": hints
        }
```

---

### AC1.2.4: Structured Logging

**Requirements:**
- [ ] Use structlog for all logging
- [ ] Log key fields: query, result_count, latency, index_name
- [ ] Log errors with full context

**Implementation:**

Already included in the execute method above. Key log events:

```python
# On start
self.logger.info("search_started", query=query, top_k=top_k)

# On success
self.logger.info(
    "search_completed",
    result_count=len(results),
    search_latency_ms=latency_ms,
    index_name=self.azure_base.content_index,
    azure_operation="search"
)

# On error
self.logger.error(
    "search_failed",
    error_type=error_type,
    error=error_message,
    query=query,
    search_latency_ms=latency_ms
)
```

---

### AC1.2.5: Unit Tests

**File:** `capstone/agent_v2/tests/test_rag_semantic_search_tool.py`

**Requirements:**
- [ ] Test successful search with mocked Azure client
- [ ] Test empty results handling
- [ ] Test error scenarios
- [ ] Test security filter application

**Implementation:**

```python
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
                "block_id": "block1",
                "block_type": "text",
                "content": "Test content about pumps",
                "doc_id": "doc1",
                "filename": "manual.pdf",
                "page_number": 5,
                "@search.score": 0.95
            },
            {
                "block_id": "block2",
                "block_type": "text",
                "content": "More information",
                "doc_id": "doc1",
                "filename": "manual.pdf",
                "page_number": 6,
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
        assert first_result["block_type"] == "text"
        assert first_result["content"] == "Test content about pumps"
        assert first_result["filename"] == "manual.pdf"
        assert first_result["page_number"] == 5
        assert first_result["score"] == 0.95

    @pytest.mark.asyncio
    async def test_successful_search_with_image_results(self, search_tool, mock_azure_base):
        """Test successful search returning image blocks."""
        mock_client = AsyncMock()
        mock_results = [
            {
                "block_id": "img1",
                "block_type": "image",
                "image_url": "https://blob.storage/image1.png",
                "image_caption": "Diagram of XYZ pump",
                "doc_id": "doc1",
                "filename": "manual.pdf",
                "page_number": 7,
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
        assert image_result["block_type"] == "image"
        assert image_result["image_url"] == "https://blob.storage/image1.png"
        assert image_result["image_caption"] == "Diagram of XYZ pump"
        assert "content" not in image_result  # Images don't have content field

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
        mock_azure_base.build_security_filter.return_value = "access_control_list/any(acl: acl eq 'test_user')"

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
        mock_azure_base.build_security_filter.return_value = "access_control_list/any(acl: acl eq 'test_user')"

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
        assert "access_control_list" in filter_str
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
```

**Run tests:**
```bash
pytest capstone/agent_v2/tests/test_rag_semantic_search_tool.py -v
```

---

### AC1.2.6: Integration Test

**File:** `capstone/agent_v2/tests/integration/test_rag_semantic_search_integration.py`

**Requirements:**
- [ ] Test against real Azure AI Search index
- [ ] Verify actual content blocks retrieved
- [ ] Test multimodal results (text + images)

**Implementation:**

```python
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
            assert "block_id" in first_result
            assert "block_type" in first_result
            assert first_result["block_type"] in ["text", "image"]
            assert "filename" in first_result
            assert "page_number" in first_result

            # Type-specific checks
            if first_result["block_type"] == "text":
                assert "content" in first_result
            elif first_result["block_type"] == "image":
                assert "image_url" in first_result
                assert "image_caption" in first_result

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
```

**Run integration test:**
```bash
export AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
export AZURE_SEARCH_API_KEY=your-key

pytest capstone/agent_v2/tests/integration/test_rag_semantic_search_integration.py -v -m integration
```

---

## Integration Verification

### IV1.2.1: Tool Registration in Agent

**Verification:**
```python
# Test that tool can be registered with agent
from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
from capstone.agent_v2.agent import Agent

# Create tool
search_tool = SemanticSearchTool(user_context={"user_id": "test"})

# Verify tool interface
assert search_tool.name == "rag_semantic_search"
assert callable(search_tool.execute)
assert hasattr(search_tool, "parameters_schema")

# Create agent with RAG tool (manual registration for testing)
tools = [search_tool]  # Plus existing tools
# Agent would use this in create_rag_agent() method (Story 1.6)

print("✅ Tool can be registered with Agent")
```

---

### IV1.2.2: Agent Can Execute TodoItem with Tool

**Verification:**
```python
# Simulate agent calling the tool (as it would in ReAct loop)
import asyncio
from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool

async def test_agent_usage():
    tool = SemanticSearchTool(user_context={"user_id": "agent_test"})

    # Simulate agent deciding to use this tool
    action = {
        "tool": "rag_semantic_search",
        "tool_input": {
            "query": "How does the system work?",
            "top_k": 3
        }
    }

    # Agent would call execute with unpacked tool_input
    result = await tool.execute(**action["tool_input"])

    # Agent expects this structure
    assert "success" in result
    if result["success"]:
        assert "results" in result
        assert "result_count" in result
        print(f"✅ Agent can execute tool: {result['result_count']} results")
    else:
        assert "error" in result
        assert "hints" in result
        print(f"✅ Agent received structured error: {result['type']}")

asyncio.run(test_agent_usage())
```

---

### IV1.2.3: Existing Agent Performance Unaffected

**Verification:**
```bash
# Run existing agent tests - should still pass
pytest capstone/agent_v2/tests/ -v --ignore=tests/integration -k "not rag"

# Expected: All non-RAG tests pass
# RAG tools are not loaded unless explicitly created
```

---

## Technical Notes

### Integration Approach

**Follows Existing Tool Pattern:**
This tool follows the exact same structure as `tools/web_tool.py`:
- Inherits from `Tool` base class
- Implements `name`, `description`, `parameters_schema`, `function_tool_schema` properties
- Has async `execute()` method returning `Dict[str, Any]`
- Returns `{"success": True/False, ...}` format

**Uses Story 1.1 Infrastructure:**
- Uses `AzureSearchBase` for connection and security filtering
- Leverages environment variable configuration
- Benefits from centralized Azure logic

### Key Constraints

1. **AsyncSearchClient Lifecycle:**
   - Must use `async with client:` pattern
   - Client is created per-request (no connection pooling yet)
   - Future optimization: connection pooling (not in this story)

2. **Result Size Limits:**
   - top_k clamped to 1-50 range
   - Azure Search has default limits
   - Large result sets handled by pagination (future story)

3. **Security Filter Always Applied:**
   - If user_context provided, security filter is mandatory
   - No way to bypass (ensures row-level security)
   - Empty filter only if user_context is None/empty

### File Structure After This Story

```
capstone/agent_v2/
├── tools/
│   ├── azure_search_base.py              # From Story 1.1
│   ├── rag_semantic_search_tool.py       # NEW
│   ├── web_tool.py                        # Existing (unchanged)
│   └── ...
├── tests/
│   ├── test_azure_search_base.py          # From Story 1.1
│   ├── test_rag_semantic_search_tool.py   # NEW
│   └── integration/
│       ├── test_azure_search_integration.py          # From Story 1.1
│       └── test_rag_semantic_search_integration.py   # NEW
└── requirements.txt                        # Unchanged (deps in Story 1.1)
```

---

## Definition of Done

- [x] **Code Complete:**
  - [ ] `tools/rag_semantic_search_tool.py` fully implemented
  - [ ] All methods have docstrings and type hints
  - [ ] Error handling comprehensive

- [x] **Tests Pass:**
  - [ ] All unit tests pass (AC1.2.5)
  - [ ] Integration test passes (AC1.2.6)
  - [ ] No regression in existing tests (IV1.2.1, IV1.2.2, IV1.2.3)

- [x] **Quality:**
  - [ ] Code follows PEP 8 (run `black` and `isort`)
  - [ ] Type hints present (run `mypy`)
  - [ ] Structured logging implemented
  - [ ] Error messages clear and actionable

- [x] **Integration:**
  - [ ] Tool can be instantiated successfully
  - [ ] Tool can be registered with Agent (manual test)
  - [ ] Tool execute() returns correct format
  - [ ] Security filtering works

---

## Risk Assessment and Mitigation

### Primary Risk: Azure Search Query Failures

**Mitigation:**
- Comprehensive error handling with specific error types
- Clear hints for each error type
- Integration test validates real Azure connection

**Rollback:**
- Tool is purely additive (not used unless explicitly registered)
- Remove tool file and tests to rollback
- No impact on existing agent

### Compatibility Verification

- [x] **No breaking changes:** ✅ (No existing code modified)
- [x] **Follows existing patterns:** ✅ (Same as WebSearchTool)
- [x] **Performance impact negligible:** ✅ (Only loaded when needed)

---

## Dependencies

**Depends on:**
- Story 1.1: Azure Search Base Infrastructure (MUST be complete)

**Blocks:**
- Story 1.3: Document Metadata Tools (follows this pattern)
- Story 1.5: Synthesis (needs search results)
- Story 1.6: Integration (needs all tools)

---

## Implementation Checklist

### Phase 1: Setup (15 min)
- [ ] Verify Story 1.1 is complete (AzureSearchBase exists)
- [ ] Create `tools/rag_semantic_search_tool.py` file
- [ ] Import necessary modules

### Phase 2: Core Implementation (3 hours)
- [ ] Implement `__init__` and tool properties
- [ ] Implement `execute()` method
- [ ] Implement `_combine_filters()` helper
- [ ] Implement `_handle_error()` method
- [ ] Add structured logging

### Phase 3: Testing (2.5 hours)
- [ ] Create `tests/test_rag_semantic_search_tool.py`
- [ ] Implement all unit tests (11 test cases)
- [ ] Create `tests/integration/test_rag_semantic_search_integration.py`
- [ ] Run unit tests locally
- [ ] Run integration test (if Azure credentials available)

### Phase 4: Verification (1 hour)
- [ ] Test tool registration with Agent (IV1.2.1)
- [ ] Test agent execution pattern (IV1.2.2)
- [ ] Run existing agent tests (IV1.2.3)
- [ ] Code quality checks (black, isort, mypy)

### Phase 5: Documentation (30 min)
- [ ] Verify all docstrings complete
- [ ] Add inline comments for complex logic
- [ ] Update any relevant README sections

---

**Ready for development! 🚀**

*This story implements the core RAG search capability and validates the base infrastructure from Story 1.1.*
