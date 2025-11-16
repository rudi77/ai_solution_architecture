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
                        "content_id": "...",
                        "content_type": "text" | "image" | "unknown",
                        "document_id": "...",
                        "document_title": "...",
                        "document_type": "application/pdf",
                        "page_number": 5,
                        "score": 0.85,
                        "org_id": "...",
                        "user_id": "...",
                        "scope": "shared",
                        "content": "..." (if text),
                        "content_path": "..." (if image),
                        "content_text": "..." (image description if image)
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
                        "content_id",
                        "content_text",
                        "text_document_id",
                        "image_document_id",
                        "content_path",
                        "document_id",
                        "document_title",
                        "document_type",
                        "locationMetadata",
                        "org_id",
                        "user_id",
                        "scope"
                    ],
                    include_total_count=True
                )

                # Process results
                results = []
                async for result in search_results:
                    # Determine content type based on presence of text_document_id vs image_document_id
                    is_text = bool(result.get("text_document_id"))
                    is_image = bool(result.get("image_document_id"))

                    # Extract page number from nested locationMetadata
                    page_number = None
                    location_metadata = result.get("locationMetadata")
                    if location_metadata and isinstance(location_metadata, dict):
                        page_number = location_metadata.get("pageNumber")

                    block = {
                        "content_id": result.get("content_id"),
                        "content_type": "text" if is_text else ("image" if is_image else "unknown"),
                        "document_id": result.get("document_id"),
                        "document_title": result.get("document_title"),
                        "document_type": result.get("document_type"),
                        "page_number": page_number,
                        "score": result.get("@search.score", 0.0),
                        "org_id": result.get("org_id"),
                        "user_id": result.get("user_id"),
                        "scope": result.get("scope")
                    }

                    # Add type-specific fields
                    if is_text:
                        block["content"] = result.get("content_text", "")
                    elif is_image:
                        block["content_path"] = result.get("content_path", "")
                        block["content_text"] = result.get("content_text", "")  # Image description

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
            index_name=self.azure_base.content_index,
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
