"""
Unit Tests for LeanAgent

Tests the LeanAgent class using protocol mocks to verify the simplified
ReAct loop without TodoListManager, QueryRouter, or ReplanStrategy.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from taskforce.core.domain.lean_agent import LeanAgent
from taskforce.core.domain.events import ActionType
from taskforce.core.domain.models import ExecutionResult
from taskforce.core.tools.planner_tool import PlannerTool


@pytest.fixture
def mock_state_manager():
    """Mock StateManagerProtocol."""
    mock = AsyncMock()
    mock.load_state.return_value = {"answers": {}}
    mock.save_state.return_value = True
    return mock


@pytest.fixture
def mock_llm_provider():
    """Mock LLMProviderProtocol."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_tool():
    """Mock ToolProtocol for a generic tool."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool for unit tests"
    tool.parameters_schema = {"type": "object", "properties": {}}
    tool.execute = AsyncMock(return_value={"success": True, "output": "test result"})
    return tool


@pytest.fixture
def planner_tool():
    """Real PlannerTool for testing plan management."""
    return PlannerTool()


@pytest.fixture
def lean_agent(mock_state_manager, mock_llm_provider, mock_tool, planner_tool):
    """Create LeanAgent with mocked dependencies."""
    return LeanAgent(
        state_manager=mock_state_manager,
        llm_provider=mock_llm_provider,
        tools=[mock_tool, planner_tool],
        system_prompt="You are a helpful assistant.",
    )


class TestLeanAgentInitialization:
    """Tests for LeanAgent initialization."""

    def test_initializes_with_dependencies(self, lean_agent, mock_tool):
        """Test agent initializes with correct dependencies."""
        assert lean_agent.state_manager is not None
        assert lean_agent.llm_provider is not None
        assert "test_tool" in lean_agent.tools
        assert "planner" in lean_agent.tools
        assert lean_agent.system_prompt == "You are a helpful assistant."

    def test_creates_planner_if_not_provided(self, mock_state_manager, mock_llm_provider):
        """Test that PlannerTool is created if not provided."""
        agent = LeanAgent(
            state_manager=mock_state_manager,
            llm_provider=mock_llm_provider,
            tools=[],  # No tools provided
            system_prompt="Test prompt",
        )
        assert "planner" in agent.tools
        assert isinstance(agent._planner, PlannerTool)


class TestLeanAgentExecution:
    """Tests for LeanAgent.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_simple_respond_action(
        self, lean_agent, mock_llm_provider, mock_state_manager
    ):
        """Test that execute completes when LLM returns respond action."""
        # Setup: LLM returns respond action immediately
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": json.dumps({
                "action": "respond",
                "summary": "Hello! How can I help you today?",
            }),
        }

        # Execute
        result = await lean_agent.execute(
            mission="Say hello",
            session_id="test-session",
        )

        # Verify
        assert isinstance(result, ExecutionResult)
        assert result.status == "completed"
        assert result.final_message == "Hello! How can I help you today?"
        assert result.session_id == "test-session"
        mock_state_manager.save_state.assert_called()

    @pytest.mark.asyncio
    async def test_execute_tool_call_then_respond(
        self, lean_agent, mock_llm_provider, mock_tool
    ):
        """Test tool execution followed by respond action."""
        # Setup: First call returns tool_call, second returns respond
        mock_llm_provider.complete.side_effect = [
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "test_tool",
                    "tool_input": {"param": "value"},
                }),
            },
            {
                "success": True,
                "content": json.dumps({
                    "action": "respond",
                    "summary": "Task completed successfully.",
                }),
            },
        ]

        # Execute
        result = await lean_agent.execute(
            mission="Do something with test_tool",
            session_id="test-session",
        )

        # Verify
        assert result.status == "completed"
        assert result.final_message == "Task completed successfully."
        mock_tool.execute.assert_called_once_with(param="value")

    @pytest.mark.asyncio
    async def test_execute_with_planner_tool(
        self, lean_agent, mock_llm_provider, planner_tool
    ):
        """Test execution with PlannerTool for plan management."""
        # Setup: LLM creates plan, marks done, then responds
        mock_llm_provider.complete.side_effect = [
            # Step 1: Create plan
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "planner",
                    "tool_input": {
                        "action": "create_plan",
                        "tasks": ["Step 1: Do X", "Step 2: Do Y"],
                    },
                }),
            },
            # Step 2: Mark first step done
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "planner",
                    "tool_input": {"action": "mark_done", "step_index": 1},
                }),
            },
            # Step 3: Mark second step done
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "planner",
                    "tool_input": {"action": "mark_done", "step_index": 2},
                }),
            },
            # Step 4: Respond with summary
            {
                "success": True,
                "content": json.dumps({
                    "action": "respond",
                    "summary": "All steps completed!",
                }),
            },
        ]

        # Execute
        result = await lean_agent.execute(
            mission="Complete the two-step process",
            session_id="test-session",
        )

        # Verify
        assert result.status == "completed"
        assert result.final_message == "All steps completed!"
        
        # Verify plan state after execution
        plan_result = planner_tool._read_plan()
        assert "[x] 1." in plan_result["output"]
        assert "[x] 2." in plan_result["output"]

    @pytest.mark.asyncio
    async def test_execute_ask_user_pauses_execution(
        self, lean_agent, mock_llm_provider, mock_state_manager
    ):
        """Test that ask_user action pauses execution."""
        # Setup: LLM asks user a question
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": json.dumps({
                "action": "ask_user",
                "question": "What is your name?",
                "answer_key": "user_name",
            }),
        }

        # Execute
        result = await lean_agent.execute(
            mission="Get user name",
            session_id="test-session",
        )

        # Verify
        assert result.status == "paused"
        assert result.final_message == "What is your name?"
        assert result.pending_question is not None
        assert result.pending_question["question"] == "What is your name?"
        assert result.pending_question["answer_key"] == "user_name"

    @pytest.mark.asyncio
    async def test_execute_handles_tool_not_found(
        self, lean_agent, mock_llm_provider
    ):
        """Test graceful handling when tool is not found."""
        # Setup: LLM calls non-existent tool, then responds
        mock_llm_provider.complete.side_effect = [
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "nonexistent_tool",
                    "tool_input": {},
                }),
            },
            {
                "success": True,
                "content": json.dumps({
                    "action": "respond",
                    "summary": "Recovered from error.",
                }),
            },
        ]

        # Execute
        result = await lean_agent.execute(
            mission="Use nonexistent tool",
            session_id="test-session",
        )

        # Verify: Agent should continue and eventually respond
        assert result.status == "completed"
        # Check execution history for error observation
        error_obs = [
            h for h in result.execution_history
            if h["type"] == "observation" and h["data"].get("error")
        ]
        assert len(error_obs) == 1
        assert "Tool not found" in error_obs[0]["data"]["error"]

    @pytest.mark.asyncio
    async def test_execute_respects_max_steps(
        self, lean_agent, mock_llm_provider
    ):
        """Test that execution stops at MAX_STEPS."""
        lean_agent.MAX_STEPS = 3  # Set low for test

        # Setup: LLM always returns tool_call (never responds)
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": json.dumps({
                "action": "tool_call",
                "tool": "test_tool",
                "tool_input": {},
            }),
        }

        # Execute
        result = await lean_agent.execute(
            mission="Infinite loop test",
            session_id="test-session",
        )

        # Verify: Should fail due to max steps
        assert result.status == "failed"
        assert "Exceeded maximum steps" in result.final_message


class TestLeanAgentStatePersistence:
    """Tests for state persistence including PlannerTool state."""

    @pytest.mark.asyncio
    async def test_planner_state_persisted(
        self, lean_agent, mock_llm_provider, mock_state_manager, planner_tool
    ):
        """Test that PlannerTool state is saved with session state."""
        # Setup: Create plan and respond
        mock_llm_provider.complete.side_effect = [
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "planner",
                    "tool_input": {
                        "action": "create_plan",
                        "tasks": ["Task A", "Task B"],
                    },
                }),
            },
            {
                "success": True,
                "content": json.dumps({
                    "action": "respond",
                    "summary": "Plan created.",
                }),
            },
        ]

        # Execute
        await lean_agent.execute(mission="Create plan", session_id="test-session")

        # Verify: State should include planner_state
        saved_state = mock_state_manager.save_state.call_args[0][1]
        assert "planner_state" in saved_state
        assert "tasks" in saved_state["planner_state"]
        assert len(saved_state["planner_state"]["tasks"]) == 2

    @pytest.mark.asyncio
    async def test_planner_state_restored(
        self, mock_state_manager, mock_llm_provider, mock_tool
    ):
        """Test that PlannerTool state is restored from session state."""
        # Setup: State with existing planner state
        mock_state_manager.load_state.return_value = {
            "answers": {},
            "planner_state": {
                "tasks": [
                    {"description": "Existing task", "status": "PENDING"},
                ],
            },
        }

        # Setup: LLM reads plan then responds
        mock_llm_provider.complete.side_effect = [
            {
                "success": True,
                "content": json.dumps({
                    "action": "tool_call",
                    "tool": "planner",
                    "tool_input": {"action": "read_plan"},
                }),
            },
            {
                "success": True,
                "content": json.dumps({
                    "action": "respond",
                    "summary": "Found existing plan.",
                }),
            },
        ]

        # Create agent and execute
        planner = PlannerTool()
        agent = LeanAgent(
            state_manager=mock_state_manager,
            llm_provider=mock_llm_provider,
            tools=[mock_tool, planner],
            system_prompt="Test",
        )

        await agent.execute(mission="Check plan", session_id="test-session")

        # Verify: Planner should have restored state
        result = planner._read_plan()
        assert "Existing task" in result["output"]


class TestLeanAgentThoughtParsing:
    """Tests for thought/action parsing from LLM responses."""

    @pytest.mark.asyncio
    async def test_parse_minimal_schema(self, lean_agent, mock_llm_provider):
        """Test parsing of minimal schema response."""
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": json.dumps({
                "action": "respond",
                "summary": "Test response",
            }),
        }

        result = await lean_agent.execute(
            mission="Test",
            session_id="test-session",
        )

        assert result.status == "completed"
        assert result.final_message == "Test response"

    @pytest.mark.asyncio
    async def test_parse_handles_invalid_json(self, lean_agent, mock_llm_provider):
        """Test graceful handling of invalid JSON response."""
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": "This is not valid JSON",
        }

        result = await lean_agent.execute(
            mission="Test",
            session_id="test-session",
        )

        # Should return with fallback respond action
        assert result.status == "completed"
        assert "Failed to parse" in result.final_message or "try again" in result.final_message.lower()

    @pytest.mark.asyncio
    async def test_parse_normalizes_legacy_finish_step(
        self, lean_agent, mock_llm_provider
    ):
        """Test that legacy 'finish_step' is normalized to 'respond'."""
        mock_llm_provider.complete.return_value = {
            "success": True,
            "content": json.dumps({
                "action": "finish_step",  # Legacy action type
                "summary": "Step finished",
            }),
        }

        result = await lean_agent.execute(
            mission="Test",
            session_id="test-session",
        )

        assert result.status == "completed"
        assert result.final_message == "Step finished"


class TestLeanAgentNoLegacyDependencies:
    """Tests verifying LeanAgent has no legacy dependencies."""

    def test_no_todolist_manager_attribute(self, lean_agent):
        """Verify LeanAgent has no todolist_manager attribute."""
        assert not hasattr(lean_agent, "todolist_manager")

    def test_no_router_attribute(self, lean_agent):
        """Verify LeanAgent has no router attribute."""
        assert not hasattr(lean_agent, "_router")
        assert not hasattr(lean_agent, "router")

    def test_no_fast_path_methods(self, lean_agent):
        """Verify LeanAgent has no fast-path methods."""
        assert not hasattr(lean_agent, "_execute_fast_path")
        assert not hasattr(lean_agent, "_execute_full_path")
        assert not hasattr(lean_agent, "_generate_fast_path_thought")

    def test_no_replan_method(self, lean_agent):
        """Verify LeanAgent has no _replan method."""
        assert not hasattr(lean_agent, "_replan")

