"""
Agent factory module for creating specialized agent instances.

This module provides builder functions for different agent types:
- create_standard_agent(): General-purpose agent with web, git, file, and shell tools
- create_rag_agent(): Specialized agent for document retrieval and knowledge search
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import litellm

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool


def create_standard_agent(
    name: str,
    description: str,
    system_prompt: Optional[str] = None,
    mission: Optional[str] = None,
    work_dir: str = "./agent_work",
    llm = None
) -> Agent:
    """
    Create a general-purpose agent with standard tools.
    
    Standard tools include:
    - WebSearchTool: Search the web for information
    - WebFetchTool: Fetch content from URLs
    - PythonTool: Execute Python code
    - GitHubTool: Interact with GitHub repositories
    - GitTool: Perform git operations
    - FileReadTool: Read files from disk
    - FileWriteTool: Write files to disk
    - PowerShellTool: Execute PowerShell commands
    - LLMTool: Generate text using LLM
    
    Args:
        name: The name of the agent.
        description: The description of the agent.
        system_prompt: The system prompt for the agent (defaults to GENERIC_SYSTEM_PROMPT).
        mission: The mission for the agent.
        work_dir: The work directory for the agent (default: ./agent_work).
        llm: The LLM instance to use (default: litellm).
    
    Returns:
        Agent instance configured with standard tools.
    
    Example:
        >>> agent = create_standard_agent(
        ...     name="Research Assistant",
        ...     description="Helps with research tasks",
        ...     mission="Find information about Python async patterns"
        ... )
    """
    if llm is None:
        llm = litellm
    
    # Create standard tool set
    tools = [
        WebSearchTool(),
        WebFetchTool(),
        PythonTool(),
        GitHubTool(),
        GitTool(),
        FileReadTool(),
        FileWriteTool(),
        PowerShellTool(),
        LLMTool(llm=llm),
    ]
    
    return Agent.create_agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        mission=mission,
        tools=tools,
        work_dir=work_dir,
        llm=llm
    )


def create_rag_agent(
    session_id: str,
    user_context: Optional[Dict[str, Any]] = None,
    work_dir: Optional[str] = None,
    llm = None
) -> Agent:
    """
    Create an agent with RAG capabilities for document search and retrieval.
    
    RAG tools include:
    - SemanticSearchTool: Search documents using semantic similarity
    - ListDocumentsTool: List available documents
    - GetDocumentTool: Retrieve full document content
    - LLMTool: Generate text using LLM
    
    Args:
        session_id: Unique session identifier for the agent.
        user_context: User context for security filtering (user_id, org_id, scope).
        work_dir: Working directory for state and todolists (default: ./rag_agent_work).
        llm: LLM instance to use (default: litellm).
    
    Returns:
        Agent instance configured with RAG tools and system prompt.
    
    Example:
        >>> agent = create_rag_agent(
        ...     session_id="rag_session_001",
        ...     user_context={"user_id": "user123", "org_id": "org456", "scope": "shared"}
        ... )
        >>> async for event in agent.execute("What does the manual say about pumps?", session_id):
        ...     print(event)
    """
    from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
    from capstone.agent_v2.tools.rag_list_documents_tool import ListDocumentsTool
    from capstone.agent_v2.tools.rag_get_document_tool import GetDocumentTool
    from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT
    
    if llm is None:
        llm = litellm
    
    # Create RAG tools with user context
    rag_tools = [
        SemanticSearchTool(user_context=user_context),
        ListDocumentsTool(user_context=user_context),
        GetDocumentTool(user_context=user_context),
        LLMTool(llm=llm)
    ]
    
    # Set default work directory
    if work_dir is None:
        work_dir = "./rag_agent_work"
    
    return Agent.create_agent(
        name="RAG Knowledge Assistant",
        description="Agent with semantic search capabilities for enterprise documents",
        system_prompt=RAG_SYSTEM_PROMPT,
        mission=None,  # Mission will be set per execute() call
        tools=rag_tools,
        work_dir=work_dir,
        llm=llm
    )

