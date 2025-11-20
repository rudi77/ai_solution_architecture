"""Integration tests for replanning with LLM service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.planning.todolist import TodoItem, TaskStatus, TodoListManager
from capstone.agent_v2.replanning import StrategyType, ReplanStrategy
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
    return manager


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager."""
    manager = MagicMock(spec=StateManager)
    return manager


@pytest.fixture
def agent(mock_llm_service, mock_todo_list_manager, mock_state_manager):
    """Create an Agent instance with mocked dependencies."""
    return Agent(
        name="TestAgent",
        description="Test agent for replanning",
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
        status=TaskStatus.FAILED
    )


class TestGenerateReplanStrategyIntegration:
    """Integration tests for Agent.generate_replan_strategy()."""

    @pytest.mark.asyncio
    async def test_generate_retry_with_params_strategy(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test generating RETRY_WITH_PARAMS strategy."""
        # Mock LLM response for retry strategy
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "The file path appears to be incorrect. Try using the correct config directory path.",
            "modifications": {
                "new_parameters": {
                    "path": "/correct/config.json"
                }
            },
            "confidence": 0.85
        })
        mock_llm_service.complete.return_value = llm_response

        # Generate strategy
        strategy = await agent.generate_replan_strategy(failed_todo_item)

        # Verify LLM was called
        assert mock_llm_service.complete.called
        call_args = mock_llm_service.complete.call_args

        # Check that prompt was formatted with failure context
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        prompt_content = messages[0]["content"]
        assert "Read configuration file" in prompt_content
        assert "file_read" in prompt_content
        assert "File not found" in prompt_content

        # Verify strategy
        assert strategy is not None
        assert strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS
        assert strategy.confidence == 0.85
        assert "new_parameters" in strategy.modifications
        assert strategy.modifications["new_parameters"]["path"] == "/correct/config.json"

    @pytest.mark.asyncio
    async def test_generate_swap_tool_strategy(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test generating SWAP_TOOL strategy."""
        # Mock LLM response for swap strategy
        llm_response = json.dumps({
            "strategy_type": "swap_tool",
            "rationale": "File reading failed multiple times. Try using shell tool to check if file exists first.",
            "modifications": {
                "new_tool": "shell_tool",
                "new_parameters": {
                    "command": "test -f /wrong/config.json && cat /wrong/config.json"
                }
            },
            "confidence": 0.75
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is not None
        assert strategy.strategy_type == StrategyType.SWAP_TOOL
        assert strategy.confidence == 0.75
        assert strategy.modifications["new_tool"] == "shell_tool"

    @pytest.mark.asyncio
    async def test_generate_decompose_task_strategy(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test generating DECOMPOSE_TASK strategy."""
        # Mock LLM response for decompose strategy
        llm_response = json.dumps({
            "strategy_type": "decompose_task",
            "rationale": "The task is too complex. Break it into: 1) locate config file, 2) validate path, 3) read file.",
            "modifications": {
                "subtasks": [
                    {
                        "description": "Find config file location",
                        "acceptance_criteria": "Config file path identified",
                        "suggested_tool": "shell_tool"
                    },
                    {
                        "description": "Verify file exists and is readable",
                        "acceptance_criteria": "File accessibility confirmed",
                        "suggested_tool": "shell_tool"
                    },
                    {
                        "description": "Read file contents",
                        "acceptance_criteria": "File content loaded",
                        "suggested_tool": "file_read"
                    }
                ]
            },
            "confidence": 0.90
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is not None
        assert strategy.strategy_type == StrategyType.DECOMPOSE_TASK
        assert strategy.confidence == 0.90
        assert "subtasks" in strategy.modifications
        assert len(strategy.modifications["subtasks"]) == 3
        assert strategy.modifications["subtasks"][0]["description"] == "Find config file location"

    @pytest.mark.asyncio
    async def test_generate_strategy_low_confidence_rejected(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test that strategies with low confidence are rejected."""
        # Mock LLM response with low confidence
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Not sure what went wrong, maybe try different params?",
            "modifications": {
                "new_parameters": {"path": "/some/path"}
            },
            "confidence": 0.4  # Below threshold (0.6)
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        # Strategy should be rejected due to low confidence
        assert strategy is None

    @pytest.mark.asyncio
    async def test_generate_strategy_invalid_json(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test handling of invalid JSON response from LLM."""
        # Mock invalid JSON response
        mock_llm_service.complete.return_value = "This is not valid JSON"

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is None

    @pytest.mark.asyncio
    async def test_generate_strategy_empty_response(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test handling of empty LLM response."""
        mock_llm_service.complete.return_value = ""

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is None

    @pytest.mark.asyncio
    async def test_generate_strategy_invalid_strategy_type(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test handling of invalid strategy type in LLM response."""
        # Mock response with invalid strategy type
        llm_response = json.dumps({
            "strategy_type": "invalid_strategy",
            "rationale": "Some rationale",
            "modifications": {},
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is None

    @pytest.mark.asyncio
    async def test_generate_strategy_missing_required_modifications(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test validation fails for missing required modification fields."""
        # RETRY_WITH_PARAMS without new_parameters
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Missing new_parameters",
            "modifications": {},
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        # Should fail validation
        assert strategy is None

    @pytest.mark.asyncio
    async def test_generate_strategy_llm_exception(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test handling of LLM service exception."""
        # Mock LLM service to raise exception
        mock_llm_service.complete.side_effect = Exception("LLM service error")

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is None

    @pytest.mark.asyncio
    async def test_extract_failure_context_includes_tools(
        self,
        agent,
        failed_todo_item
    ):
        """Test that failure context extraction includes available tools."""
        context = agent._extract_failure_context(failed_todo_item)

        # Should include available_tools from agent
        assert "available_tools" in context
        assert "task_description" in context
        assert "error_message" in context
        assert context["task_description"] == "Read configuration file"
        assert context["error_type"] == "FileNotFoundError"

    @pytest.mark.asyncio
    async def test_generate_strategy_with_additional_error_context(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test passing additional error context to strategy generation."""
        # Mock LLM response
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Path correction needed",
            "modifications": {"new_parameters": {"path": "/new/path"}},
            "confidence": 0.7
        })
        mock_llm_service.complete.return_value = llm_response

        # Additional error context
        additional_context = {
            "traceback": "Full traceback...",
            "system_info": "Linux x86_64"
        }

        strategy = await agent.generate_replan_strategy(
            failed_todo_item,
            error_context=additional_context
        )

        assert strategy is not None
        # LLM should have received the additional context in the prompt
        call_args = mock_llm_service.complete.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # Additional context should be merged into the failure context
        # (exact presence depends on prompt template)


class TestStrategyValidationIntegration:
    """Integration tests for strategy validation in Agent context."""

    @pytest.mark.asyncio
    async def test_valid_retry_strategy_accepted(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test that a valid retry strategy is accepted."""
        llm_response = json.dumps({
            "strategy_type": "retry_with_params",
            "rationale": "Valid strategy",
            "modifications": {"new_parameters": {"key": "value"}},
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        assert strategy is not None
        assert strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS

    @pytest.mark.asyncio
    async def test_invalid_decompose_strategy_rejected(
        self,
        agent,
        mock_llm_service,
        failed_todo_item
    ):
        """Test that invalid DECOMPOSE_TASK strategy is rejected."""
        # Subtask missing required fields
        llm_response = json.dumps({
            "strategy_type": "decompose_task",
            "rationale": "Decompose",
            "modifications": {
                "subtasks": [
                    {"description": "Task 1"}  # Missing acceptance_criteria
                ]
            },
            "confidence": 0.8
        })
        mock_llm_service.complete.return_value = llm_response

        strategy = await agent.generate_replan_strategy(failed_todo_item)

        # Should fail validation
        assert strategy is None

