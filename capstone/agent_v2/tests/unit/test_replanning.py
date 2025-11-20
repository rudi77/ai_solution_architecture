"""Unit tests for the replanning module."""

import json
import pytest

from capstone.agent_v2.replanning import (
    StrategyType,
    ReplanStrategy,
    validate_strategy,
    extract_failure_context,
    MIN_CONFIDENCE_THRESHOLD,
    REPLAN_PROMPT_TEMPLATE,
)
from capstone.agent_v2.planning.todolist import TodoItem, TaskStatus


class TestStrategyType:
    """Tests for StrategyType enum."""

    def test_strategy_type_values(self):
        """Test that all strategy types have expected values."""
        assert StrategyType.RETRY_WITH_PARAMS.value == "retry_with_params"
        assert StrategyType.SWAP_TOOL.value == "swap_tool"
        assert StrategyType.DECOMPOSE_TASK.value == "decompose_task"

    def test_strategy_type_from_string(self):
        """Test creating strategy type from string value."""
        assert StrategyType("retry_with_params") == StrategyType.RETRY_WITH_PARAMS
        assert StrategyType("swap_tool") == StrategyType.SWAP_TOOL
        assert StrategyType("decompose_task") == StrategyType.DECOMPOSE_TASK


class TestReplanStrategy:
    """Tests for ReplanStrategy dataclass."""

    def test_strategy_creation(self):
        """Test creating a ReplanStrategy instance."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.RETRY_WITH_PARAMS,
            rationale="File path was incorrect",
            modifications={"new_parameters": {"path": "/correct/path"}},
            confidence=0.85
        )

        assert strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS
        assert strategy.rationale == "File path was incorrect"
        assert strategy.modifications == {"new_parameters": {"path": "/correct/path"}}
        assert strategy.confidence == 0.85

    def test_strategy_to_dict(self):
        """Test converting strategy to dictionary."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.SWAP_TOOL,
            rationale="Different tool needed",
            modifications={"new_tool": "git_tool", "new_parameters": {}},
            confidence=0.7
        )

        result = strategy.to_dict()

        assert result["strategy_type"] == "swap_tool"
        assert result["rationale"] == "Different tool needed"
        assert result["modifications"]["new_tool"] == "git_tool"
        assert result["confidence"] == 0.7

    def test_strategy_to_json(self):
        """Test serializing strategy to JSON."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.DECOMPOSE_TASK,
            rationale="Task too complex",
            modifications={"subtasks": [{"description": "Step 1", "acceptance_criteria": "Done"}]},
            confidence=0.9
        )

        json_str = strategy.to_json()
        parsed = json.loads(json_str)

        assert parsed["strategy_type"] == "decompose_task"
        assert parsed["confidence"] == 0.9
        assert len(parsed["modifications"]["subtasks"]) == 1

    def test_strategy_from_dict_valid(self):
        """Test creating strategy from valid dictionary."""
        data = {
            "strategy_type": "retry_with_params",
            "rationale": "Test rationale",
            "modifications": {"new_parameters": {"key": "value"}},
            "confidence": 0.75
        }

        strategy = ReplanStrategy.from_dict(data)

        assert strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS
        assert strategy.rationale == "Test rationale"
        assert strategy.confidence == 0.75

    def test_strategy_from_dict_missing_strategy_type(self):
        """Test from_dict raises ValueError for missing strategy_type."""
        data = {
            "rationale": "Test",
            "modifications": {},
            "confidence": 0.8
        }

        with pytest.raises(ValueError, match="Invalid or missing strategy_type"):
            ReplanStrategy.from_dict(data)

    def test_strategy_from_dict_invalid_strategy_type(self):
        """Test from_dict raises ValueError for invalid strategy_type."""
        data = {
            "strategy_type": "invalid_type",
            "rationale": "Test",
            "modifications": {},
            "confidence": 0.8
        }

        with pytest.raises(ValueError, match="Invalid or missing strategy_type"):
            ReplanStrategy.from_dict(data)

    def test_strategy_from_dict_defaults(self):
        """Test from_dict uses defaults for optional fields."""
        data = {
            "strategy_type": "swap_tool"
        }

        strategy = ReplanStrategy.from_dict(data)

        assert strategy.strategy_type == StrategyType.SWAP_TOOL
        assert strategy.rationale == ""
        assert strategy.modifications == {}
        assert strategy.confidence == 0.0


class TestValidateStrategy:
    """Tests for validate_strategy function."""

    def test_validate_retry_with_params_valid(self):
        """Test validation passes for valid RETRY_WITH_PARAMS strategy."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.RETRY_WITH_PARAMS,
            rationale="Valid retry",
            modifications={"new_parameters": {"param": "value"}},
            confidence=0.8
        )

        assert validate_strategy(strategy) is True

    def test_validate_retry_with_params_missing_new_parameters(self):
        """Test validation fails for RETRY_WITH_PARAMS without new_parameters."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.RETRY_WITH_PARAMS,
            rationale="Missing params",
            modifications={},
            confidence=0.8
        )

        assert validate_strategy(strategy) is False

    def test_validate_swap_tool_valid(self):
        """Test validation passes for valid SWAP_TOOL strategy."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.SWAP_TOOL,
            rationale="Valid swap",
            modifications={"new_tool": "python_tool", "new_parameters": {}},
            confidence=0.75
        )

        assert validate_strategy(strategy) is True

    def test_validate_swap_tool_missing_new_tool(self):
        """Test validation fails for SWAP_TOOL without new_tool."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.SWAP_TOOL,
            rationale="Missing tool",
            modifications={"new_parameters": {}},
            confidence=0.8
        )

        assert validate_strategy(strategy) is False

    def test_validate_decompose_task_valid(self):
        """Test validation passes for valid DECOMPOSE_TASK strategy."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.DECOMPOSE_TASK,
            rationale="Valid decomposition",
            modifications={
                "subtasks": [
                    {
                        "description": "Subtask 1",
                        "acceptance_criteria": "Criteria 1",
                        "suggested_tool": "file_tool"
                    },
                    {
                        "description": "Subtask 2",
                        "acceptance_criteria": "Criteria 2"
                    }
                ]
            },
            confidence=0.85
        )

        assert validate_strategy(strategy) is True

    def test_validate_decompose_task_missing_subtasks(self):
        """Test validation fails for DECOMPOSE_TASK without subtasks."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.DECOMPOSE_TASK,
            rationale="Missing subtasks",
            modifications={},
            confidence=0.8
        )

        assert validate_strategy(strategy) is False

    def test_validate_decompose_task_invalid_subtask_format(self):
        """Test validation fails for DECOMPOSE_TASK with invalid subtask."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.DECOMPOSE_TASK,
            rationale="Invalid subtask",
            modifications={
                "subtasks": [
                    {"description": "Task 1"}  # Missing acceptance_criteria
                ]
            },
            confidence=0.8
        )

        assert validate_strategy(strategy) is False

    def test_validate_decompose_task_subtask_not_dict(self):
        """Test validation fails when subtask is not a dictionary."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.DECOMPOSE_TASK,
            rationale="Subtask not dict",
            modifications={
                "subtasks": ["invalid"]
            },
            confidence=0.8
        )

        assert validate_strategy(strategy) is False

    def test_validate_low_confidence(self):
        """Test validation fails for confidence below threshold."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.RETRY_WITH_PARAMS,
            rationale="Low confidence",
            modifications={"new_parameters": {}},
            confidence=0.5  # Below MIN_CONFIDENCE_THRESHOLD (0.6)
        )

        assert validate_strategy(strategy) is False

    def test_validate_confidence_at_threshold(self):
        """Test validation passes for confidence at threshold."""
        strategy = ReplanStrategy(
            strategy_type=StrategyType.RETRY_WITH_PARAMS,
            rationale="At threshold",
            modifications={"new_parameters": {}},
            confidence=MIN_CONFIDENCE_THRESHOLD
        )

        assert validate_strategy(strategy) is True


class TestExtractFailureContext:
    """Tests for extract_failure_context function."""

    def test_extract_basic_context(self):
        """Test extracting basic failure context."""
        todo_item = TodoItem(
            position=1,
            description="Read file from disk",
            acceptance_criteria="File content loaded",
            chosen_tool="file_read",
            tool_input={"path": "/wrong/path.txt"},
            execution_result={
                "success": False,
                "error": "File not found",
                "error_type": "FileNotFoundError"
            },
            attempts=2
        )

        context = extract_failure_context(todo_item)

        assert context["task_description"] == "Read file from disk"
        assert context["acceptance_criteria"] == "File content loaded"
        assert context["tool_name"] == "file_read"
        assert '"path": "/wrong/path.txt"' in context["parameters"]
        assert context["error_message"] == "File not found"
        assert context["error_type"] == "FileNotFoundError"
        assert context["attempt_count"] == 2

    def test_extract_context_with_stdout_stderr(self):
        """Test extraction includes stdout/stderr when present."""
        todo_item = TodoItem(
            position=1,
            description="Run script",
            acceptance_criteria="Script succeeds",
            chosen_tool="shell_tool",
            tool_input={"command": "test.py"},
            execution_result={
                "success": False,
                "error": "Script failed",
                "error_type": "RuntimeError",
                "stdout": "Processing...",
                "stderr": "Error: Invalid input"
            },
            attempts=1
        )

        context = extract_failure_context(todo_item)

        assert context["stdout"] == "Processing..."
        assert context["stderr"] == "Error: Invalid input"

    def test_extract_context_no_execution_result(self):
        """Test extraction handles missing execution_result."""
        todo_item = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Done",
            execution_result=None,
            attempts=0
        )

        context = extract_failure_context(todo_item)

        assert context["error_message"] == "No error message available"
        assert context["error_type"] == "unknown"
        assert context["tool_name"] == "unknown"

    def test_extract_context_with_additional_context(self):
        """Test extraction merges additional error context."""
        todo_item = TodoItem(
            position=1,
            description="Task",
            acceptance_criteria="Done",
            execution_result={"success": False, "error": "Failed"},
            attempts=1
        )

        additional = {
            "traceback": "Full traceback here...",
            "custom_field": "custom value"
        }

        context = extract_failure_context(todo_item, additional)

        assert context["traceback"] == "Full traceback here..."
        assert context["custom_field"] == "custom value"
        # Original fields should still be present
        assert context["task_description"] == "Task"


class TestPromptTemplate:
    """Tests for REPLAN_PROMPT_TEMPLATE."""

    def test_prompt_template_format(self):
        """Test that prompt template can be formatted with all required fields."""
        context = {
            "task_description": "Test task",
            "acceptance_criteria": "Test criteria",
            "tool_name": "test_tool",
            "parameters": '{"key": "value"}',
            "error_message": "Test error",
            "error_type": "TestError",
            "attempt_count": 1,
            "available_tools": "tool1, tool2"
        }

        prompt = REPLAN_PROMPT_TEMPLATE.format(**context)

        assert "Test task" in prompt
        assert "Test criteria" in prompt
        assert "test_tool" in prompt
        assert "Test error" in prompt
        assert "TestError" in prompt
        assert "tool1, tool2" in prompt

    def test_prompt_template_includes_strategy_types(self):
        """Test that prompt template describes all strategy types."""
        assert "RETRY_WITH_PARAMS" in REPLAN_PROMPT_TEMPLATE
        assert "SWAP_TOOL" in REPLAN_PROMPT_TEMPLATE
        assert "DECOMPOSE_TASK" in REPLAN_PROMPT_TEMPLATE

    def test_prompt_template_includes_confidence_guidance(self):
        """Test that prompt template includes confidence scoring guidance."""
        assert "confidence" in REPLAN_PROMPT_TEMPLATE.lower()
        assert "0.6" in REPLAN_PROMPT_TEMPLATE  # Threshold mentioned


class TestConstants:
    """Tests for module constants."""

    def test_min_confidence_threshold(self):
        """Test MIN_CONFIDENCE_THRESHOLD is reasonable."""
        assert MIN_CONFIDENCE_THRESHOLD == 0.6
        assert 0.0 <= MIN_CONFIDENCE_THRESHOLD <= 1.0

    def test_strategy_generation_timeout(self):
        """Test STRATEGY_GENERATION_TIMEOUT is reasonable."""
        from capstone.agent_v2.replanning import STRATEGY_GENERATION_TIMEOUT
        assert STRATEGY_GENERATION_TIMEOUT == 5.0
        assert STRATEGY_GENERATION_TIMEOUT > 0

