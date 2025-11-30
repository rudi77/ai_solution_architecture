"""
Unit Tests for Core Agent ReAct Loop

Tests the Agent class using protocol mocks to verify ReAct logic
without any I/O or infrastructure dependencies.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from taskforce.core.domain.agent import Agent
from taskforce.core.domain.events import ActionType
from taskforce.core.domain.models import ExecutionResult
from taskforce.core.interfaces.todolist import TaskStatus, TodoItem, TodoList


@pytest.fixture
def mock_state_manager():
    """Mock StateManagerProtocol."""
    mock = AsyncMock()
    mock.load_state.return_value = {"answers": {}}
    mock.save_state.return_value = None
    return mock


@pytest.fixture
def mock_llm_provider():
    """Mock LLMProviderProtocol."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_todolist_manager():
    """Mock TodoListManagerProtocol."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_tool():
    """Mock ToolProtocol."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.parameters_schema = {"type": "object", "properties": {}}
    tool.execute = AsyncMock(return_value={"success": True, "output": "test result"})
    return tool


@pytest.fixture
def agent(mock_state_manager, mock_llm_provider, mock_tool, mock_todolist_manager):
    """Create Agent with mocked dependencies."""
    return Agent(
        state_manager=mock_state_manager,
        llm_provider=mock_llm_provider,
        tools=[mock_tool],
        todolist_manager=mock_todolist_manager,
        system_prompt="Test system prompt",
    )


@pytest.mark.asyncio
async def test_agent_initialization(agent, mock_tool):
    """Test agent initializes with correct dependencies."""
    assert agent.state_manager is not None
    assert agent.llm_provider is not None
    assert agent.todolist_manager is not None
    assert "test_tool" in agent.tools
    assert agent.tools["test_tool"] == mock_tool
    assert agent.system_prompt == "Test system prompt"


@pytest.mark.asyncio
async def test_execute_creates_todolist_on_first_run(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider
):
    """Test that execute creates a TodoList on first run."""
    # Setup: State has no todolist_id
    mock_state_manager.load_state.return_value = {"answers": {}}

    # Setup: TodoList with one completed item
    todolist = TodoList(
        todolist_id="test-todolist-123",
        items=[
            TodoItem(
                position=1,
                description="Test task",
                acceptance_criteria="Task completed",
                dependencies=[],
                status=TaskStatus.COMPLETED,
                execution_result={"success": True},
            )
        ],
        open_questions=[],
        notes="Test notes",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify TodoList was created
    mock_todolist_manager.create_todolist.assert_called_once()
    call_args = mock_todolist_manager.create_todolist.call_args
    assert call_args.kwargs["mission"] == "Test mission"
    assert "tools_desc" in call_args.kwargs

    # Verify state was saved with todolist_id
    assert mock_state_manager.save_state.called
    saved_state = mock_state_manager.save_state.call_args_list[0][0][1]
    assert saved_state["todolist_id"] == "test-todolist-123"

    # Verify result
    assert isinstance(result, ExecutionResult)
    assert result.session_id == "test-session"
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_execute_loads_existing_todolist(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider
):
    """Test that execute loads existing TodoList if todolist_id in state and items pending."""
    # Setup: State has todolist_id
    mock_state_manager.load_state.return_value = {
        "todolist_id": "existing-todolist-456",
        "answers": {},
    }

    # Setup: Existing TodoList with PENDING item (not completed, so it resumes)
    todolist = TodoList(
        todolist_id="existing-todolist-456",
        items=[
            TodoItem(
                position=1,
                description="Existing task",
                acceptance_criteria="Task done",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.load_todolist.return_value = todolist

    # LLM returns finish_step to complete the pending task
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps({
            "step_ref": 1,
            "rationale": "Task already done",
            "action": {"type": "finish_step"},
            "expected_outcome": "Complete",
            "confidence": 1.0,
        }),
    }

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify TodoList was loaded, not created
    mock_todolist_manager.load_todolist.assert_called_with("existing-todolist-456")
    mock_todolist_manager.create_todolist.assert_not_called()

    # Verify result
    assert result.todolist_id == "existing-todolist-456"


@pytest.mark.asyncio
async def test_react_loop_executes_pending_step(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test ReAct loop executes a pending step with tool_call then finish_step."""
    # Setup state
    mock_state_manager.load_state.return_value = {"answers": {}}

    # Setup TodoList with one pending item
    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Execute test tool",
                acceptance_criteria="Tool executed successfully",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # Setup LLM to return tool_call first, then finish_step
    tool_call_response = {
        "step_ref": 1,
        "rationale": "Need to execute the test tool",
        "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {"param": "value"}},
        "expected_outcome": "Tool executes successfully",
        "confidence": 0.9,
    }
    finish_step_response = {
        "step_ref": 1,
        "rationale": "Tool succeeded, marking step complete",
        "action": {"type": "finish_step"},
        "expected_outcome": "Step is done",
        "confidence": 1.0,
    }
    mock_llm_provider.complete.side_effect = [
        {"success": True, "content": json.dumps(tool_call_response)},
        {"success": True, "content": json.dumps(finish_step_response)},
    ]

    # Setup tool to succeed
    mock_tool.execute.return_value = {"success": True, "output": "test result"}

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify LLM was called twice (tool_call + finish_step)
    assert mock_llm_provider.complete.call_count == 2

    # Verify tool was executed once (tool_input is spread as kwargs)
    mock_tool.execute.assert_called_once_with(param="value")

    # Verify TodoList was updated
    assert mock_todolist_manager.update_todolist.called
    updated_todolist = mock_todolist_manager.update_todolist.call_args[0][0]
    assert updated_todolist.items[0].status == TaskStatus.COMPLETED
    assert updated_todolist.items[0].chosen_tool == "test_tool"

    # Verify result
    assert result.status == "completed"
    assert len(result.execution_history) > 0


@pytest.mark.asyncio
async def test_react_loop_handles_ask_user_action(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider
):
    """Test ReAct loop pauses when ask_user action is generated."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Need user input",
                acceptance_criteria="User provides answer",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns ask_user action
    thought_response = {
        "step_ref": 1,
        "rationale": "Need to ask user for input",
        "action": {
            "type": "ask_user",
            "question": "What is your name?",
            "answer_key": "user_name",
        },
        "expected_outcome": "User provides their name",
        "confidence": 1.0,
    }
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps(thought_response),
    }

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify execution paused
    assert result.status == "paused"
    # Final message is the actual question when pending_question exists
    assert result.final_message == "What is your name?"

    # Verify pending question was stored in state
    save_calls = mock_state_manager.save_state.call_args_list
    # Find the call that saved pending_question
    pending_question_saved = False
    for call in save_calls:
        state_arg = call[0][1]
        if "pending_question" in state_arg:
            assert state_arg["pending_question"]["question"] == "What is your name?"
            assert state_arg["pending_question"]["answer_key"] == "user_name"
            pending_question_saved = True
            break
    assert pending_question_saved


@pytest.mark.asyncio
async def test_react_loop_handles_complete_action(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider
):
    """Test ReAct loop handles early completion with complete action."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Complete immediately",
                acceptance_criteria="Mission done",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns complete action
    thought_response = {
        "step_ref": 1,
        "rationale": "Mission is already complete",
        "action": {"type": "complete", "summary": "Task completed successfully"},
        "expected_outcome": "Mission marked as complete",
        "confidence": 1.0,
    }
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps(thought_response),
    }

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify early completion
    assert result.status == "completed"
    assert result.final_message == "Task completed successfully"

    # Verify TodoList was updated (step gets marked as completed first, then skipped)
    # The complete action marks the current step as completed via observation processing
    # Then marks all PENDING steps as skipped (but this step is already completed)
    assert mock_todolist_manager.update_todolist.called


@pytest.mark.asyncio
async def test_react_loop_retries_failed_step(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test ReAct loop retries a failed step."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Retry test",
                acceptance_criteria="Tool succeeds",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns tool_call actions, then finish_step after success
    tool_call_response = {
        "step_ref": 1,
        "rationale": "Execute tool",
        "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
        "expected_outcome": "Tool succeeds",
        "confidence": 0.9,
    }
    finish_step_response = {
        "step_ref": 1,
        "rationale": "Tool succeeded",
        "action": {"type": "finish_step"},
        "expected_outcome": "Done",
        "confidence": 1.0,
    }
    mock_llm_provider.complete.side_effect = [
        {"success": True, "content": json.dumps(tool_call_response)},  # First attempt
        {"success": True, "content": json.dumps(tool_call_response)},  # Retry
        {"success": True, "content": json.dumps(finish_step_response)},  # Finish
    ]

    # Tool fails first time, succeeds second time
    mock_tool.execute.side_effect = [
        {"success": False, "error": "First attempt failed"},
        {"success": True, "output": "Success on retry"},
    ]

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify tool was called twice (initial + retry)
    assert mock_tool.execute.call_count == 2

    # Verify final status is completed
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_react_loop_respects_max_attempts(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test ReAct loop respects max_attempts limit."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Fail repeatedly",
                acceptance_criteria="Tool succeeds",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=2,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns tool_call action
    thought_response = {
        "step_ref": 1,
        "rationale": "Execute tool",
        "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
        "expected_outcome": "Tool succeeds",
        "confidence": 0.9,
    }
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps(thought_response),
    }

    # Tool always fails
    mock_tool.execute.return_value = {"success": False, "error": "Always fails"}

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify tool was called max_attempts times
    assert mock_tool.execute.call_count == 2

    # Verify final status is failed
    assert result.status == "failed"

    # Verify step is marked as FAILED
    updated_todolist = mock_todolist_manager.update_todolist.call_args[0][0]
    assert updated_todolist.items[0].status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_react_loop_respects_dependencies(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test ReAct loop respects step dependencies."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="First step",
                acceptance_criteria="Step 1 done",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            ),
            TodoItem(
                position=2,
                description="Second step (depends on 1)",
                acceptance_criteria="Step 2 done",
                dependencies=[1],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            ),
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns tool_call then finish_step for each step
    mock_llm_provider.complete.side_effect = [
        {"success": True, "content": json.dumps({
            "step_ref": 1,
            "rationale": "Execute step 1",
            "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
            "expected_outcome": "Step 1 completes",
            "confidence": 0.9,
        })},
        {"success": True, "content": json.dumps({
            "step_ref": 1,
            "rationale": "Step 1 done",
            "action": {"type": "finish_step"},
            "expected_outcome": "Complete",
            "confidence": 1.0,
        })},
        {"success": True, "content": json.dumps({
            "step_ref": 2,
            "rationale": "Execute step 2",
            "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
            "expected_outcome": "Step 2 completes",
            "confidence": 0.9,
        })},
        {"success": True, "content": json.dumps({
            "step_ref": 2,
            "rationale": "Step 2 done",
            "action": {"type": "finish_step"},
            "expected_outcome": "Complete",
            "confidence": 1.0,
        })},
    ]

    mock_tool.execute.return_value = {"success": True, "output": "success"}

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify both steps were executed in order
    assert mock_tool.execute.call_count == 2

    # Verify both steps completed
    assert result.status == "completed"
    updated_todolist = mock_todolist_manager.update_todolist.call_args[0][0]
    assert updated_todolist.items[0].status == TaskStatus.COMPLETED
    assert updated_todolist.items[1].status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_react_loop_stops_at_max_iterations(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test ReAct loop stops at MAX_ITERATIONS to prevent infinite loops."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    # Create a TodoList that never completes (always returns PENDING)
    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Never completes",
                acceptance_criteria="Impossible",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=100,  # High limit
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM always returns tool_call
    thought_response = {
        "step_ref": 1,
        "rationale": "Keep trying",
        "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
        "expected_outcome": "Eventually succeeds",
        "confidence": 0.5,
    }
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps(thought_response),
    }

    # Tool always fails
    mock_tool.execute.return_value = {"success": False, "error": "Always fails"}

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify execution stopped at MAX_ITERATIONS
    assert result.status == "failed"
    assert "maximum iterations" in result.final_message.lower()


@pytest.mark.asyncio
async def test_get_next_actionable_step_skips_completed(agent):
    """Test _get_next_actionable_step skips completed steps."""
    todolist = TodoList(
        todolist_id="test",
        items=[
            TodoItem(
                position=1,
                description="Completed",
                acceptance_criteria="Done",
                dependencies=[],
                status=TaskStatus.COMPLETED,
                execution_history=[],
            ),
            TodoItem(
                position=2,
                description="Pending",
                acceptance_criteria="Not done",
                dependencies=[],
                status=TaskStatus.PENDING,
                execution_history=[],
            ),
        ],
        open_questions=[],
        notes="",
    )

    next_step = agent._get_next_actionable_step(todolist)

    assert next_step is not None
    assert next_step.position == 2


@pytest.mark.asyncio
async def test_get_next_actionable_step_respects_dependencies(agent):
    """Test _get_next_actionable_step respects dependencies."""
    todolist = TodoList(
        todolist_id="test",
        items=[
            TodoItem(
                position=1,
                description="First",
                acceptance_criteria="Done",
                dependencies=[],
                status=TaskStatus.PENDING,
                execution_history=[],
            ),
            TodoItem(
                position=2,
                description="Second (depends on 1)",
                acceptance_criteria="Done",
                dependencies=[1],
                status=TaskStatus.PENDING,
                execution_history=[],
            ),
        ],
        open_questions=[],
        notes="",
    )

    next_step = agent._get_next_actionable_step(todolist)

    # Should return step 1 first (no dependencies)
    assert next_step.position == 1

    # Mark step 1 as completed
    todolist.items[0].status = TaskStatus.COMPLETED

    next_step = agent._get_next_actionable_step(todolist)

    # Now should return step 2
    assert next_step.position == 2


@pytest.mark.asyncio
async def test_is_plan_complete(agent):
    """Test _is_plan_complete correctly identifies completed plans."""
    # All completed
    todolist = TodoList(
        todolist_id="test",
        items=[
            TodoItem(
                position=1,
                description="Task 1",
                acceptance_criteria="Done",
                dependencies=[],
                status=TaskStatus.COMPLETED,
                execution_history=[],
            ),
            TodoItem(
                position=2,
                description="Task 2",
                acceptance_criteria="Done",
                dependencies=[],
                status=TaskStatus.COMPLETED,
                execution_history=[],
            ),
        ],
        open_questions=[],
        notes="",
    )

    assert agent._is_plan_complete(todolist) is True

    # Some pending
    todolist.items[1].status = TaskStatus.PENDING
    assert agent._is_plan_complete(todolist) is False

    # Some skipped (should still be complete)
    todolist.items[1].status = TaskStatus.SKIPPED
    assert agent._is_plan_complete(todolist) is True


# ============================================================================
# FINISH_STEP Tests - Autonomous Kernel Infrastructure
# ============================================================================


@pytest.mark.asyncio
async def test_action_type_includes_finish_step():
    """Test that ActionType enum includes FINISH_STEP."""
    assert ActionType.FINISH_STEP == "finish_step"
    assert ActionType.FINISH_STEP.value == "finish_step"


@pytest.mark.asyncio
async def test_tool_success_keeps_step_pending(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test that successful tool execution keeps step PENDING (not COMPLETED).
    
    This is the core behavior change: tool success != step completion.
    The agent must explicitly emit FINISH_STEP to complete a step.
    """
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Test step",
                acceptance_criteria="Must be verified",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns tool_call (NOT finish_step)
    thought_response = {
        "step_ref": 1,
        "rationale": "Execute tool first",
        "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
        "expected_outcome": "Tool executes",
        "confidence": 0.9,
    }
    
    # After tool success, LLM emits finish_step
    finish_response = {
        "step_ref": 1,
        "rationale": "Tool succeeded, step is done",
        "action": {"type": "finish_step"},
        "expected_outcome": "Step marked complete",
        "confidence": 1.0,
    }
    
    mock_llm_provider.complete.side_effect = [
        {"success": True, "content": json.dumps(thought_response)},
        {"success": True, "content": json.dumps(finish_response)},
    ]

    # Tool succeeds
    mock_tool.execute.return_value = {"success": True, "output": "done"}

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify: LLM was called twice (tool_call, then finish_step)
    assert mock_llm_provider.complete.call_count == 2

    # Verify: step ends up COMPLETED only after finish_step
    assert result.status == "completed"
    updated_todolist = mock_todolist_manager.update_todolist.call_args[0][0]
    assert updated_todolist.items[0].status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_tool_success_resets_attempts_counter(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider, mock_tool
):
    """Test that successful tool execution resets attempts counter to 0.
    
    This allows extended workflows without hitting retry limits.
    The execution_history records attempt counts at each step, which proves the reset.
    """
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Test step",
                acceptance_criteria="Verified",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=2,  # Start with some attempts already used
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM returns tool_call then finish_step
    mock_llm_provider.complete.side_effect = [
        {"success": True, "content": json.dumps({
            "step_ref": 1,
            "rationale": "Execute tool",
            "action": {"type": "tool_call", "tool": "test_tool", "tool_input": {}},
            "expected_outcome": "Success",
            "confidence": 0.9,
        })},
        {"success": True, "content": json.dumps({
            "step_ref": 1,
            "rationale": "Done",
            "action": {"type": "finish_step"},
            "expected_outcome": "Complete",
            "confidence": 1.0,
        })},
    ]

    mock_tool.execute.return_value = {"success": True, "output": "done"}

    # Execute
    await agent.execute(mission="Test mission", session_id="test-session")

    # Verify reset happened by checking execution_history
    # The execution_history records attempt count at each call:
    # - First entry: tool_call with attempt=3 (2+1 before reset)
    # - Second entry: finish_step with attempt=1 (0+1 after reset)
    step = todolist.items[0]
    assert len(step.execution_history) == 2
    
    # First call recorded attempt 3 (started at 2, incremented to 3)
    assert step.execution_history[0]["attempt"] == 3
    
    # After reset to 0, finish_step incremented to 1
    # This proves the reset happened between the two calls
    assert step.execution_history[1]["attempt"] == 1


@pytest.mark.asyncio
async def test_finish_step_completes_step_explicitly(
    agent, mock_state_manager, mock_todolist_manager, mock_llm_provider
):
    """Test that FINISH_STEP action explicitly completes a step."""
    # Setup
    mock_state_manager.load_state.return_value = {"answers": {}}

    todolist = TodoList(
        todolist_id="test-todolist",
        items=[
            TodoItem(
                position=1,
                description="Complete explicitly",
                acceptance_criteria="Done",
                dependencies=[],
                status=TaskStatus.PENDING,
                attempts=0,
                max_attempts=3,
                execution_history=[],
            )
        ],
        open_questions=[],
        notes="",
    )
    mock_todolist_manager.create_todolist.return_value = todolist

    # LLM directly emits finish_step (e.g., if step was already satisfied)
    thought_response = {
        "step_ref": 1,
        "rationale": "Step requirements already met",
        "action": {"type": "finish_step"},
        "expected_outcome": "Step marked complete",
        "confidence": 1.0,
    }
    mock_llm_provider.complete.return_value = {
        "success": True,
        "content": json.dumps(thought_response),
    }

    # Execute
    result = await agent.execute(mission="Test mission", session_id="test-session")

    # Verify step is COMPLETED
    assert result.status == "completed"
    updated_todolist = mock_todolist_manager.update_todolist.call_args[0][0]
    assert updated_todolist.items[0].status == TaskStatus.COMPLETED
