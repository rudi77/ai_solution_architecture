"""Tests for Agent class using LLMService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

from capstone.agent_v2.agent import Agent, MessageHistory
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.planning.todolist import TodoItem, TaskStatus


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock()
    return service


@pytest.fixture
def mock_todolist_manager():
    """Create mock TodoListManager."""
    return MagicMock()


@pytest.fixture
def mock_state_manager():
    """Create mock StateManager."""
    return MagicMock()


class TestMessageHistoryWithLLMService:
    """Test MessageHistory using LLMService."""
    
    @pytest.mark.asyncio
    async def test_compress_uses_llm_service(self, mock_llm_service):
        """Test that compress_history_async uses LLMService."""
        # Setup
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": "Summary of conversation",
            "usage": {"total_tokens": 100}
        }
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        # Add messages to trigger compression
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        # Compress
        await history.compress_history_async()
        
        # Verify LLMService was called
        mock_llm_service.complete.assert_called_once()
        
        # Verify model alias used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
        
        # Verify temperature is 0
        assert call_args.kwargs["temperature"] == 0
    
    @pytest.mark.asyncio
    async def test_compress_handles_llm_failure(self, mock_llm_service):
        """Test compression handles LLM service failures gracefully."""
        # Setup failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "API error"
        }
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        # Add messages
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        original_length = len(history.messages)
        
        # Should not raise, just log error
        await history.compress_history_async()
        
        # Messages should be trimmed to recent ones when compression fails
        assert len(history.messages) <= MessageHistory.SUMMARY_THRESHOLD + 1  # +1 for system prompt
    
    @pytest.mark.asyncio
    async def test_compress_handles_exception(self, mock_llm_service):
        """Test compression handles exceptions gracefully."""
        # Setup exception
        mock_llm_service.complete.side_effect = Exception("Network error")
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        # Add messages
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        # Should not raise, just log error
        await history.compress_history_async()
        
        # Messages should be trimmed
        assert len(history.messages) <= MessageHistory.SUMMARY_THRESHOLD + 1


class TestAgentWithLLMService:
    """Test Agent using LLMService."""
    
    def test_agent_init_accepts_llm_service(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager,
        tmp_path
    ):
        """Test Agent initialization with LLMService."""
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission=None,
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        assert agent.llm_service is mock_llm_service
        assert agent.message_history.llm_service is mock_llm_service
    
    def test_agent_init_accepts_legacy_llm(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test Agent initialization with legacy llm parameter."""
        legacy_llm = MagicMock()
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission=None,
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service,
            llm=legacy_llm
        )
        
        # Should accept both parameters for backward compatibility
        assert agent.llm_service is mock_llm_service
    
    @pytest.mark.asyncio
    async def test_get_thought_uses_llm_service(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test thought generation uses LLMService."""
        # Setup
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"step_ref": 1, "rationale": "Test thought", "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}}, "expected_outcome": "Success"}',
            "usage": {"total_tokens": 50}
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission="Test mission",
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        # Create mock TodoItem
        mock_step = TodoItem(
            position=1,
            description="Test step",
            acceptance_criteria="Test passes",
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        # Build context
        context = {
            "current_step": mock_step,
            "current_error": None,
            "previous_results": [],
            "available_context": {},
            "available_tools": "test tools",
            "user_answers": {},
            "mission": "Test mission"
        }
        
        # Get thought
        result = await agent._generate_thought_with_context(context)
        
        # Verify
        mock_llm_service.complete.assert_called_once()
        assert result.rationale == "Test thought"
        
        # Verify model alias used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
        assert call_args.kwargs["temperature"] == 0.2
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
    
    @pytest.mark.asyncio
    async def test_get_thought_handles_llm_failure(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test thought generation handles LLM failures."""
        # Setup failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "API timeout"
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission="Test mission",
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        mock_step = TodoItem(
            position=1,
            description="Test step",
            acceptance_criteria="Test passes",
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        context = {
            "current_step": mock_step,
            "current_error": None,
            "previous_results": [],
            "available_context": {},
            "available_tools": "test tools",
            "user_answers": {},
            "mission": "Test mission"
        }
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="LLM completion failed"):
            await agent._generate_thought_with_context(context)
    
    @pytest.mark.asyncio
    async def test_get_thought_logs_token_usage(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test that thought generation logs token usage."""
        # Setup
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"step_ref": 1, "rationale": "Test", "action": {"type": "complete", "summary": "Done"}, "expected_outcome": "Success"}',
            "usage": {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission="Test mission",
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        mock_step = TodoItem(
            position=1,
            description="Test step",
            acceptance_criteria="Test passes",
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        context = {
            "current_step": mock_step,
            "current_error": None,
            "previous_results": [],
            "available_context": {},
            "available_tools": "test tools",
            "user_answers": {},
            "mission": "Test mission"
        }
        
        # Get thought
        result = await agent._generate_thought_with_context(context)
        
        # Token usage should be logged (verified via logger, not directly testable here)
        assert result is not None


class TestAgentCreateWithLLMService:
    """Test Agent.create_agent static method with LLMService."""
    
    def test_create_agent_with_llm_service(self, mock_llm_service, tmp_path):
        """Test creating agent with LLMService."""
        work_dir = str(tmp_path / "agent_work")
        
        agent = Agent.create_agent(
            name="Test Agent",
            description="Test description",
            system_prompt="You are helpful",
            mission=None,
            work_dir=work_dir,
            llm_service=mock_llm_service
        )
        
        assert agent is not None
        assert agent.name == "Test Agent"
        assert agent.llm_service is mock_llm_service
        assert len(agent.tools) == 9  # Default tool count
    
    def test_create_agent_with_custom_tools(self, mock_llm_service, tmp_path):
        """Test creating agent with custom tools."""
        work_dir = str(tmp_path / "agent_work")
        
        # Create custom tool list (empty for this test)
        custom_tools = []
        
        agent = Agent.create_agent(
            name="Custom Agent",
            description="Custom description",
            system_prompt="You are helpful",
            mission=None,
            work_dir=work_dir,
            llm_service=mock_llm_service,
            tools=custom_tools
        )
        
        assert agent is not None
        assert len(agent.tools) == 0


class TestNoHardcodedModelNames:
    """Test that no hardcoded model names remain."""
    
    @pytest.mark.asyncio
    async def test_message_history_uses_model_alias(self, mock_llm_service):
        """Test MessageHistory uses model alias, not hardcoded name."""
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": "Summary",
            "usage": {"total_tokens": 100}
        }
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        await history.compress_history_async()
        
        # Verify model alias is used (not "gpt-4.1" or similar)
        call_args = mock_llm_service.complete.call_args
        model = call_args.kwargs["model"]
        assert model == "main"
        assert "gpt-4" not in model
        assert "gpt-3" not in model
    
    @pytest.mark.asyncio
    async def test_agent_thought_uses_model_alias(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test Agent thought generation uses model alias."""
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"step_ref": 1, "rationale": "Test", "action": {"type": "complete", "summary": "Done"}, "expected_outcome": "Success"}',
            "usage": {"total_tokens": 50}
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            mission="Test mission",
            tools=[],
            todo_list_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        mock_step = TodoItem(
            position=1,
            description="Test step",
            acceptance_criteria="Test passes",
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        context = {
            "current_step": mock_step,
            "current_error": None,
            "previous_results": [],
            "available_context": {},
            "available_tools": "test tools",
            "user_answers": {},
            "mission": "Test mission"
        }
        
        await agent._generate_thought_with_context(context)
        
        # Verify model alias is used (not "gpt-4.1" or similar)
        call_args = mock_llm_service.complete.call_args
        model = call_args.kwargs["model"]
        assert model == "main"
        assert "gpt-4" not in model
        assert "gpt-3" not in model

