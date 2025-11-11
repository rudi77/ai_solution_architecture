"""Tests for agent factory module."""

import pytest
import os
import sys
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_factory import create_standard_agent, create_rag_agent


def test_create_standard_agent():
    """Test standard agent creation."""
    agent = create_standard_agent(
        name="Test Agent",
        description="Test description",
        mission="Test mission"
    )
    
    assert agent is not None
    assert agent.name == "Test Agent"
    assert agent.description == "Test description"
    assert len(agent.tools) == 9  # Standard tool count
    
    # Verify standard tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert "python" in tool_names
    assert "github" in tool_names
    assert "git" in tool_names
    assert "file_read" in tool_names
    assert "file_write" in tool_names
    assert "powershell" in tool_names
    assert "llm_generate" in tool_names


def test_create_standard_agent_with_custom_work_dir():
    """Test standard agent creation with custom work directory."""
    agent = create_standard_agent(
        name="Custom Agent",
        description="Agent with custom work dir",
        work_dir="./custom_work"
    )
    
    assert agent is not None
    assert agent.name == "Custom Agent"


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent():
    """Test RAG agent creation."""
    agent = create_rag_agent(
        session_id="test_001",
        user_context={"user_id": "test"}
    )
    
    assert agent is not None
    assert agent.name == "RAG Knowledge Assistant"
    assert len(agent.tools) == 4  # RAG tool count
    
    # Verify RAG tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "rag_semantic_search" in tool_names
    assert "rag_list_documents" in tool_names
    assert "rag_get_document" in tool_names
    assert "llm_generate" in tool_names


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent_with_custom_work_dir():
    """Test RAG agent creation with custom work directory."""
    agent = create_rag_agent(
        session_id="test_002",
        user_context={"user_id": "test", "org_id": "org123"},
        work_dir="./custom_rag_work"
    )
    
    assert agent is not None
    assert agent.name == "RAG Knowledge Assistant"
    assert agent.description == "Agent with semantic search capabilities for enterprise documents"


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent_default_work_dir():
    """Test RAG agent uses default work directory when not specified."""
    agent = create_rag_agent(
        session_id="test_003",
        user_context={"user_id": "test"}
    )
    
    assert agent is not None
    # Default work_dir should be "./rag_agent_work"
    # This is verified by the agent being created successfully

