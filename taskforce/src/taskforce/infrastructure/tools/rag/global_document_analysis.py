import asyncio
from typing import Any, Dict, List, Optional

import structlog
from taskforce.core.interfaces.tools import ApprovalRiskLevel, ToolProtocol
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.infrastructure.tools.rag.azure_search_base import AzureSearchBase
from taskforce.infrastructure.tools.rag.get_document import GetDocumentTool

class GlobalDocumentAnalysisTool(ToolProtocol):
    """
    This tool is used to handle global questions about an certain document,
    e.g. it is able to summarize the document, answer questions about the document,
    and provide a detailed analysis of the document.
    """
    def __init__(self, llm_provider: LLMProviderProtocol, get_document_tool: GetDocumentTool):
        self.llm_provider = llm_provider
        self.get_document_tool = get_document_tool
        self.azure_base = AzureSearchBase()
        self.logger = structlog.get_logger().bind(tool="global_document_analysis")

    @property
    def name(self) -> str:
        return "global_document_analysis"

    @property
    def description(self) -> str:
        return "This tool is used to handle global questions about an certain document, \
            e.g. it is able to summarize the document, answer questions about the document, \
            and provide a detailed analysis of the document."

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
                    "description": (
                        "The unique document UUID (preferred) or document title/filename. "
                        "Example: '30603b8a-9f41-47f4-9fe0-f329104faed5'"
                    )
                },
                "question": {
                    "type": "string",
                    "description": "The question to answer"
                },
                "user_context": {
                    "type": "object",
                    "description": (
                        "User context for security filtering "
                        "(org_id, user_id, scope)"
                    ),
                    "default": {}
                }
            },
            "required": ["document_id", "question"]
        }

    @property
    def requires_approval(self) -> bool:
        """Global document analysis is read-only, no approval needed."""
        return False

    @property
    def approval_risk_level(self) -> ApprovalRiskLevel:
        """Low risk - read-only operation."""
        return ApprovalRiskLevel.LOW

    def get_approval_preview(self, **kwargs: Any) -> str:
        """Generate approval preview (not used for read-only tool)."""
        document_id = kwargs.get("document_id", "")
        question = kwargs.get("question", "")
        return f"Tool: {self.name}\nOperation: Global document analysis\nDocument: {document_id}\nQuestion: {question}"

    async def execute(
        self,
        document_id: str,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute global document analysis.

        Args:
            document_id: The unique document UUID
            question: The question to answer
            user_context: Optional user context for security filtering
            **kwargs: Additional arguments (ignored)

        Returns:
            Dict with structure:
            {
                "success": True,
                "result": "Global document analysis completed"
            }
        """
        if user_context is None:
            user_context = {}

        document = await self.get_document_tool.execute(document_id, user_context=user_context)

        if not document["success"]:
            return {"success": False, "error": document["error"]}


        # 1.Get the total lenght of the chunks in the document


        # 2. If total chunks greater 50 then use map reduce and apply the question to the chunks to answer the question

        # 3. If total chunks less than 50 then immediately send the chunks and the question to the llm to answer the question

        # 4. Return the result to the user
        
        
        return {"success": True, "result": "Global document analysis completed"}

    def validate_params(self, **kwargs: Any) -> tuple[bool, str | None]:
        """Validate parameters before execution."""
        if "document_id" not in kwargs:
            return False, "Missing required parameter: document_id"
        
        if not isinstance(kwargs["document_id"], str):
            return False, "Parameter 'document_id' must be a string"
        
        if "question" not in kwargs:
            return False, "Missing required parameter: question"
        
        if not isinstance(kwargs["question"], str):
            return False, "Parameter 'question' must be a string"
