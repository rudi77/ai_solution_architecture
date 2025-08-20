"""Tests for the core ADK agent implementation."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.agent.core_agent import IDPAgent
from app.agent.events import AgentEventType
from app.agent.memory import AgentInteraction


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def agent(temp_db):
    """Create an IDPAgent instance for testing."""
    return IDPAgent(temp_db)


def test_agent_initialization(agent):
    """Test that agent initializes correctly."""
    assert agent.db_path is not None
    assert agent.memory is not None
    assert agent.git_ops is not None
    assert agent.filesystem is not None
    assert agent.template_engine is not None
    assert agent.cicd_generator is not None


def test_check_adk_availability(agent):
    """Test ADK availability checking."""
    # The actual result depends on whether ADK is installed
    availability = agent._check_adk_availability()
    assert isinstance(availability, bool)


def test_extract_repo_name(agent):
    """Test repository name extraction."""
    test_cases = [
        ("Create a repository called my-service", "my-service"),
        ("Repository name: test-api", "test-api"),
        ("Name the repo payment-service", "payment-service"),
        ("Create a new service", None),  # No specific name
    ]
    
    for message, expected in test_cases:
        result = agent._extract_repo_name(message)
        assert result == expected


def test_extract_language(agent):
    """Test programming language extraction."""
    test_cases = [
        ("Create a Go service", "go"),
        ("Build a Python API", "python"),
        ("Make a Node.js app", "node"),
        ("TypeScript service please", "typescript"),
        ("Create a service", None),  # No language specified
    ]
    
    for message, expected in test_cases:
        result = agent._extract_language(message)
        assert result == expected


def test_extract_framework(agent):
    """Test framework extraction."""
    test_cases = [
        ("Create a Go service with Gin", "gin"),
        ("FastAPI Python service", "fastapi"),
        ("Express.js application", "express"),
        ("Create a service", None),  # No framework specified
    ]
    
    for message, expected in test_cases:
        result = agent._extract_framework(message)
        assert result == expected


def test_extract_features(agent):
    """Test feature extraction."""
    test_cases = [
        ("Create a service with testing and linting", ["testing", "linting"]),
        ("Add security and metrics", ["security", "metrics"]),
        ("Basic service please", ["testing", "linting"]),  # Default features
    ]
    
    for message, expected in test_cases:
        result = agent._extract_features(message)
        assert set(result) == set(expected)


def test_extract_ci_provider(agent):
    """Test CI/CD provider extraction."""
    test_cases = [
        ("Use GitHub Actions", "github-actions"),
        ("GitLab CI please", "gitlab-ci"),
        ("Azure Pipelines", "azure-pipelines"),
        ("Create a service", "github-actions"),  # Default
    ]
    
    for message, expected in test_cases:
        result = agent._extract_ci_provider(message)
        assert result == expected


def test_check_for_clarifications(agent):
    """Test clarification detection."""
    # Message with missing info should need clarification
    result = agent._check_for_clarifications("Create a service")
    assert result["needs_clarification"] is True
    assert "repository_name" in result["missing_fields"]
    assert "language" in result["missing_fields"]
    
    # Complete message should not need clarification
    result = agent._check_for_clarifications("Create a Go service called my-api")
    assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_memory_operations(agent):
    """Test memory storage and retrieval."""
    conversation_id = "test_conv"
    
    interaction = AgentInteraction(
        id="test_interaction",
        conversation_id=conversation_id,
        user_message="Test message",
        agent_response="Test response",
        tool_calls=[],
        tool_results=[],
        reasoning="Test reasoning",
        timestamp=1234567890.0
    )
    
    # Store interaction
    await agent.memory.store_interaction(conversation_id, interaction)
    
    # Load context
    context = await agent.memory.load_context(conversation_id)
    assert len(context) == 1
    assert context[0].user_message == "Test message"
    assert context[0].agent_response == "Test response"
    
    # Clear context
    await agent.memory.clear_context(conversation_id)
    context = await agent.memory.load_context(conversation_id)
    assert len(context) == 0


@pytest.mark.asyncio
async def test_process_message_with_clarification(agent):
    """Test message processing that requires clarification."""
    conversation_id = "test_conv"
    message = "Create a service"  # Missing repo name and language
    
    events = []
    async for event in agent.process_message(conversation_id, message):
        events.append(event)
    
    # Should get a clarification event
    clarification_events = [e for e in events if e.type == AgentEventType.CLARIFICATION]
    assert len(clarification_events) > 0
    
    clarification = clarification_events[0]
    assert "repository_name" in clarification.data["required_fields"]


@pytest.mark.asyncio
async def test_process_message_complete(agent):
    """Test complete message processing without ADK."""
    conversation_id = "test_conv"
    message = "Create a Go service called test-api"
    
    events = []
    async for event in agent.process_message(conversation_id, message):
        events.append(event)
        # Break after a few events to avoid full execution in tests
        if len(events) > 3:
            break
    
    # Should have some processing events
    assert len(events) > 0
    
    # Should have thinking or tool call events
    event_types = [e.type for e in events]
    assert AgentEventType.THINKING in event_types or AgentEventType.TOOL_CALL in event_types


def test_git_operations_toolset(agent):
    """Test Git operations toolset."""
    # Test repository initialization
    result = agent.git_ops.init_repository("test-repo", "Test repository")
    
    # Should succeed or fail gracefully
    assert "success" in result
    assert isinstance(result["success"], bool)
    
    if result["success"]:
        assert "repository_name" in result
        assert result["repository_name"] == "test-repo"


def test_template_engine_toolset(agent):
    """Test template engine toolset."""
    # Test Go service generation
    result = agent.template_engine.generate_go_service("test-service", "gin", ["testing"])
    
    assert "success" in result
    assert result["success"] is True
    assert "structure" in result
    assert isinstance(result["structure"], dict)


def test_filesystem_toolset(agent):
    """Test filesystem toolset."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test file creation
        file_path = os.path.join(tmp_dir, "test.txt")
        result = agent.filesystem.create_file(file_path, "Test content")
        
        assert result["success"] is True
        assert os.path.exists(file_path)
        
        # Test file reading
        result = agent.filesystem.read_file(file_path)
        assert result["success"] is True
        assert result["content"] == "Test content"


def test_cicd_toolset(agent):
    """Test CI/CD toolset."""
    # Test GitHub Actions workflow generation
    result = agent.cicd_generator.generate_github_actions_workflow(
        "go", "gin", ["testing", "linting"]
    )
    
    assert result["success"] is True
    assert "files" in result
    assert ".github/workflows/" in list(result["files"].keys())[0]


if __name__ == "__main__":
    pytest.main([__file__])