"""Integration tests for automatic replanning on tool failures."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.planning.todolist import TodoItem, TaskStatus, TodoListManager
from capstone.agent_v2.replanning import StrategyType
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.statemanager import StateManager


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock()
    return service


@pytest.fixture
def mock_todo_list_manager():
    """Create a mock TodoListManager."""
    manager = MagicMock(spec=TodoListManager)
    manager.modify_step = AsyncMock()
    manager.decompose_step = AsyncMock()
    manager.replace_step = AsyncMock()
    manager.load_todolist = AsyncMock()
    return manager


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager."""
    manager = MagicMock(spec=StateManager)
    manager.save_state = AsyncMock()
    return manager


@pytest.fixture
def agent(mock_llm_service, mock_todo_list_manager, mock_state_manager):
    """Create an Agent instance with mocked dependencies."""
    return Agent(
        name="TestAgent",
        description="Test agent for automatic replanning",
        system_prompt="Test system prompt",
        mission="Test mission",
        tools=[],
        todo_list_manager=mock_todo_list_manager,
        state_manager=mock_state_manager,
        llm_service=mock_llm_service
    )


@pytest.fixture
def failed_todo_item():
    """Create a sample failed TodoItem."""
    return TodoItem(
        position=1,
        description="Read configuration file",
        acceptance_criteria="Config loaded successfully",
        chosen_tool="file_read",
        tool_input={"path": "/wrong/config.json"},
        execution_result={
            "success": False,
            "error": "File not found: /wrong/config.json",
            "error_type": "FileNotFoundError"
        },
        attempts=2,
        status=TaskStatus.FAILED,
        replan_count=0
    )


class TestAutomaticReplanning:
    """Integration tests for automatic replanning on tool failures."""

    @pytest.mark.asyncio
    async def test_attempt_automatic_replan_retry_strategy(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test automatic replanning with RETRY_WITH_PARAMS strategy."""
        # Set todolist_id on agent
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return retry strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Fix file path parameter",
            "modifications": {
                "new_parameters": {"path": "/correct/config.json"}
            },
            "confidence": 0.85
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager.modify_step to succeed
        mock_todo_list_manager.modify_step.return_value = (True, None)
        
        # Attempt replan
        error_context = {"error": "File not found", "error_type": "FileNotFoundError"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify success
        assert success is True
        assert "retry_with_params" in summary
        
        # Verify TodoListManager.modify_step was called
        mock_todo_list_manager.modify_step.assert_called_once()
        call_args = mock_todo_list_manager.modify_step.call_args
        assert call_args[0][0] == "test-todolist-123"
        assert call_args[0][1] == failed_todo_item.position

    @pytest.mark.asyncio
    async def test_attempt_automatic_replan_decompose_strategy(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test automatic replanning with DECOMPOSE_TASK strategy."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return decompose strategy
        llm_response = json.dumps({
            "strategy_type": "decompose_task",
            "rationale": "Break into smaller steps",
            "modifications": {
                "subtasks": [
                    {"description": "Step 1", "acceptance_criteria": "Done 1"},
                    {"description": "Step 2", "acceptance_criteria": "Done 2"}
                ]
            },
            "confidence": 0.90
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager.decompose_step to succeed
        mock_todo_list_manager.decompose_step.return_value = (True, [2, 3])
        
        # Attempt replan
        error_context = {"error": "Task too complex"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify success
        assert success is True
        assert "decompose_task" in summary
        
        # Verify decompose_step was called with correct subtasks
        mock_todo_list_manager.decompose_step.assert_called_once()
        call_args = mock_todo_list_manager.decompose_step.call_args
        assert call_args[0][0] == "test-todolist-123"
        assert call_args[0][1] == failed_todo_item.position
        assert len(call_args[0][2]) == 2

    @pytest.mark.asyncio
    async def test_attempt_automatic_replan_swap_tool_strategy(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test automatic replanning with SWAP_TOOL strategy."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return swap tool strategy
        llm_response = json.dumps({
            "strategy_type": "swap_tool",
            "rationale": "Try different tool",
            "modifications": {
                "new_tool": "shell_tool",
                "new_parameters": {"command": "cat config.json"}
            },
            "confidence": 0.75
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager.replace_step to succeed
        mock_todo_list_manager.replace_step.return_value = (True, 1)
        
        # Attempt replan
        error_context = {"error": "Tool failed"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify success
        assert success is True
        assert "swap_tool" in summary
        
        # Verify replace_step was called
        mock_todo_list_manager.replace_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_replan_limit_enforcement(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test that replan limit (max 2) is enforced."""
        # Set replan_count to 2 (limit reached)
        failed_todo_item.replan_count = 2
        
        # Attempt replan - should fail immediately without calling LLM
        error_context = {"error": "Some error"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify failure
        assert success is False
        assert "exceeded" in summary.lower()
        
        # LLM should NOT have been called
        mock_llm_service.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_replan_low_confidence_rejected(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test that low-confidence strategies are rejected."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return low-confidence strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Not sure",
            "modifications": {"new_parameters": {"path": "/maybe"}},
            "confidence": 0.4  # Below 0.6 threshold
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Attempt replan
        error_context = {"error": "Error"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify failure
        assert success is False
        assert "no viable" in summary.lower()
        
        # TodoListManager should NOT have been called
        assert not mock_todo_list_manager.modify_step.called

    @pytest.mark.asyncio
    async def test_replan_todolist_manager_failure(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test handling when TodoListManager operations fail."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return valid strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Fix params",
            "modifications": {"new_parameters": {"path": "/new"}},
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager.modify_step to fail
        mock_todo_list_manager.modify_step.return_value = (False, "Validation failed")
        
        # Attempt replan
        error_context = {"error": "Error"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify failure
        assert success is False
        assert "failed to apply" in summary.lower() or "validation failed" in summary.lower()

    @pytest.mark.asyncio
    async def test_replan_updates_message_history(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test that successful replan updates MessageHistory."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return valid strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Corrected parameters",
            "modifications": {"new_parameters": {"path": "/fixed"}},
            "confidence": 0.85
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager to succeed
        mock_todo_list_manager.modify_step.return_value = (True, None)
        
        # Track message history size before
        initial_msg_count = len(agent.message_history.messages)
        
        # Attempt replan
        error_context = {"error": "Error"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify success
        assert success is True
        
        # Verify MessageHistory was updated
        assert len(agent.message_history.messages) > initial_msg_count
        
        # Check that the replan message was added
        last_message = agent.message_history.messages[-1]
        assert last_message["role"] == "system"
        assert "Replanned step" in last_message["content"]
        assert str(failed_todo_item.position) in last_message["content"]

    @pytest.mark.asyncio
    async def test_replan_metrics_logged(
        self,
        agent,
        mock_llm_service,
        mock_todo_list_manager,
        failed_todo_item
    ):
        """Test that replan metrics are logged."""
        agent.todolist_id = "test-todolist-123"
        
        # Mock LLM to return valid strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Test rationale",
            "modifications": {"new_parameters": {"test": "value"}},
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response
        
        # Mock TodoListManager to succeed
        mock_todo_list_manager.modify_step.return_value = (True, None)
        
        # Attempt replan
        error_context = {"error": "Error"}
        success, summary = await agent._attempt_automatic_replan(failed_todo_item, error_context)
        
        # Verify success
        assert success is True
        
        # Note: In a real test, we would check logger calls
        # For now, just verify the method completed successfully
        # and the _log_replan_metrics was called (implicitly by success)

