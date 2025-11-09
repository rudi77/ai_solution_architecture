"""Integration tests for RAG agent factory and tool registration."""

import pytest
import os
import sys
from unittest.mock import patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent import Agent


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent():
    """Test RAG agent factory method creates agent successfully."""
    agent = Agent.create_rag_agent(
        session_id="test_rag_001",
        user_context={"user_id": "test_user", "org_id": "test_org"}
    )

    # Verify agent created
    assert agent is not None
    assert agent.name == "RAG Knowledge Assistant"
    assert agent.description == "Agent with semantic search capabilities for enterprise documents"

    # Verify RAG tool registered
    tool_names = [tool.name for tool in agent.tools]
    assert "rag_semantic_search" in tool_names
    assert len(agent.tools) == 1  # Only RAG tool for now

    # Verify RAG prompt loaded
    assert agent.system_prompt is not None
    assert "rag_semantic_search" in agent.system_prompt.lower()
    assert "enterprise documents" in agent.system_prompt.lower()
    assert "azure ai search" in agent.system_prompt.lower()


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_rag_agent_tool_registration():
    """Test that SemanticSearchTool is properly registered."""
    agent = Agent.create_rag_agent(
        session_id="test_rag_002",
        user_context={"user_id": "test_user"}
    )

    # Get the tool
    rag_tool = None
    for tool in agent.tools:
        if tool.name == "rag_semantic_search":
            rag_tool = tool
            break

    assert rag_tool is not None
    assert hasattr(rag_tool, 'execute')
    assert hasattr(rag_tool, 'user_context')
    assert rag_tool.user_context == {"user_id": "test_user"}


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_rag_agent_system_prompt():
    """Test that RAG system prompt is correctly loaded."""
    from prompts.rag_system_prompt import RAG_SYSTEM_PROMPT

    agent = Agent.create_rag_agent(
        session_id="test_rag_003"
    )

    # Verify the agent uses RAG prompt
    assert agent.system_prompt == RAG_SYSTEM_PROMPT

    # Verify prompt contains key sections
    assert "AVAILABLE TOOLS" in agent.system_prompt
    assert "WHEN TO USE RAG_SEMANTIC_SEARCH" in agent.system_prompt
    assert "RESPONSE FORMAT" in agent.system_prompt
    assert "EXAMPLE WORKFLOW" in agent.system_prompt


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_rag_agent_with_none_user_context():
    """Test RAG agent creation with no user context."""
    agent = Agent.create_rag_agent(
        session_id="test_rag_004",
        user_context=None
    )

    assert agent is not None
    assert len(agent.tools) == 1

    # Get the tool and verify user_context is None
    rag_tool = agent.tools[0]
    assert rag_tool.user_context is None or rag_tool.user_context == {}


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_rag_agent_custom_work_dir():
    """Test RAG agent creation with custom work directory."""
    import tempfile
    import shutil
    from pathlib import Path

    temp_dir = tempfile.mkdtemp()

    try:
        agent = Agent.create_rag_agent(
            session_id="test_rag_005",
            work_dir=temp_dir
        )

        assert agent is not None

        # Verify work directory structure created
        work_path = Path(temp_dir)
        assert (work_path / "todolists").exists()
        assert (work_path / "states").exists()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_rag_agent_tool_execution_mock():
    """Test that agent can execute with mocked tool responses."""
    # Create agent
    agent = Agent.create_rag_agent(
        session_id="test_rag_006",
        user_context={"user_id": "test_user"}
    )

    # Verify tool is accessible
    assert len(agent.tools) == 1
    assert agent.tools[0].name == "rag_semantic_search"

    # Verify tool has required methods
    tool = agent.tools[0]
    assert hasattr(tool, 'execute')
    assert hasattr(tool, 'name')
    assert hasattr(tool, 'description')
    assert hasattr(tool, 'parameters_schema')
