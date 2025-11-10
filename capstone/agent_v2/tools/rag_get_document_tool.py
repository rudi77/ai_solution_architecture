"""Get document metadata tool for Azure AI Search."""

import time
from typing import Any, Dict, Optional
import structlog

from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.azure_search_base import AzureSearchBase


class GetDocumentTool(Tool):
    """
    Retrieve detailed metadata for a specific document from content-blocks index.
    
    This tool fetches all chunks for a document and aggregates metadata including
    page count, content types, and chunk information.
    """

    def __init__(self, user_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the get document tool.

        Args:
            user_context: Optional user context for security filtering
                         (user_id, org_id, scope)
        """
        self.azure_base = AzureSearchBase()
        self.user_context = user_context or {}
        self.logger = structlog.get_logger().bind(tool="rag_get_document")

    @property
    def name(self) -> str:
        """Tool name used by the agent."""
        return "rag_get_document"

    @property
    def description(self) -> str:
        """Tool description for the agent."""
        return (
            "Retrieve detailed metadata for a specific document by document ID. "
            "Returns complete document information including title, type, chunk count, "
            "page count, content types (text/images), and access control metadata. "
            "Use this after listing documents to get detailed information about a specific document."
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
                "document_id": {
                    "type": "string",
                    "description": "The unique document identifier (UUID format)"
                },
                "user_context": {
                    "type": "object",
                    "description": "User context for security filtering (org_id, user_id, scope)",
                    "default": {}
                }
            },
            "required": ["document_id"]
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
        document_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute document metadata retrieval from content-blocks index.

        Args:
            document_id: The unique document identifier
            user_context: Optional user context override for security filtering
            **kwargs: Additional arguments (ignored)

        Returns:
            Dict with structure:
            {
                "success": True,
                "document": {
                    "document_id": "...",
                    "document_title": "...",
                    "document_type": "application/pdf",
                    "org_id": "...",
                    "user_id": "...",
                    "scope": "shared",
                    "chunk_count": 15,
                    "page_count": 7,
                    "has_images": True,
                    "has_text": True,
                    "chunks": ["content_id_1", "content_id_2", ...]
                }
            }

        Example:
            >>> tool = GetDocumentTool(user_context={"org_id": "MS-corp"})
            >>> result = await tool.execute(document_id="30603b8a-9f41-47f4-9fe0-f329104faed5")
            >>> print(result["document"]["chunk_count"])
            15
        """
        start_time = time.time()

        self.logger.info(
            "get_document_started",
            document_id=document_id
        )

        try:
            # Use provided user_context or fall back to instance context
            context = user_context or self.user_context

            # Build security filter from user context
            security_filter = self.azure_base.build_security_filter(context)

            # Build document filter
            document_filter = f"document_id eq '{self.azure_base._sanitize_filter_value(document_id)}'"
            
            # Combine with security filter
            combined_filter = document_filter
            if security_filter:
                combined_filter = f"({security_filter}) and {document_filter}"

            # Get search client for content-blocks index
            client = self.azure_base.get_search_client(
                self.azure_base.content_index
            )

            # Execute search to get all chunks for this document
            async with client:
                search_results = await client.search(
                    search_text="*",  # Match all chunks
                    filter=combined_filter,
                    select=[
                        "content_id",
                        "document_id",
                        "document_title",
                        "document_type",
                        "content_text",
                        "content_path",
                        "locationMetadata",
                        "org_id",
                        "user_id",
                        "scope"
                    ],
                    top=1000  # Get all chunks
                )

                # Aggregate chunk data
                chunks = []
                document_metadata = None
                max_page = 0
                has_text = False
                has_images = False
                chunk_ids = []

                async for chunk in search_results:
                    chunks.append(chunk)
                    chunk_ids.append(chunk.get("content_id"))

                    # Capture document metadata from first chunk
                    if document_metadata is None:
                        document_metadata = {
                            "document_id": chunk.get("document_id"),
                            "document_title": chunk.get("document_title"),
                            "document_type": chunk.get("document_type"),
                            "org_id": chunk.get("org_id"),
                            "user_id": chunk.get("user_id"),
                            "scope": chunk.get("scope")
                        }

                    # Check content types
                    if chunk.get("content_text"):
                        has_text = True
                    if chunk.get("content_path"):
                        has_images = True

                    # Extract max page number from locationMetadata
                    location_metadata = chunk.get("locationMetadata")
                    if location_metadata and isinstance(location_metadata, dict):
                        page_num = location_metadata.get("pageNumber")
                        if page_num and isinstance(page_num, (int, float)):
                            max_page = max(max_page, int(page_num))

                # Check if document was found
                if not chunks:
                    latency_ms = int((time.time() - start_time) * 1000)
                    self.logger.warning(
                        "get_document_not_found",
                        document_id=document_id,
                        search_latency_ms=latency_ms
                    )
                    return {
                        "success": False,
                        "error": "Document not found",
                        "type": "NotFoundError"
                    }

                # Build final document object
                document = {
                    **document_metadata,
                    "chunk_count": len(chunks),
                    "page_count": max_page if max_page > 0 else None,
                    "has_images": has_images,
                    "has_text": has_text,
                    "chunks": chunk_ids
                }

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            self.logger.info(
                "get_document_completed",
                azure_operation="get_document",
                index_name=self.azure_base.content_index,
                document_id=document_id,
                chunk_count=len(chunks),
                search_latency_ms=latency_ms
            )

            return {
                "success": True,
                "document": document
            }

        except Exception as e:
            return self._handle_error(e, document_id, time.time() - start_time)

    def _handle_error(
        self,
        exception: Exception,
        document_id: str,
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        Handle errors and return structured error response.

        Args:
            exception: The exception that occurred
            document_id: The document ID being retrieved
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
                hints.append("Check document_id format")
            elif exception.status_code == 403:
                error_type = "AccessDeniedError"
                hints.append("User does not have access to this document")

            error_message = f"Azure Search HTTP {exception.status_code}: {exception.message}"

        elif isinstance(exception, ServiceRequestError):
            error_type = "NetworkError"
            hints.append("Check network connectivity to Azure Search endpoint")
            hints.append(f"Endpoint: {self.azure_base.endpoint}")

        elif isinstance(exception, TimeoutError):
            error_type = "TimeoutError"
            hints.append("Request took too long")

        else:
            error_type = "AzureSearchError"
            hints.append("Check application logs for detailed traceback")

        self.logger.error(
            "get_document_failed",
            azure_operation="get_document",
            error_type=error_type,
            error=error_message,
            document_id=document_id,
            search_latency_ms=latency_ms,
            traceback=traceback.format_exc()
        )

        return {
            "success": False,
            "error": error_message,
            "type": error_type,
            "hints": hints
        }

