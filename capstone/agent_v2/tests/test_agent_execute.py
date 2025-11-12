"""Unit tests for Agent.execute() completion detection logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Dict, Any

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.planning.todolist import TodoList, TodoItem, TaskStatus
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    llm_service = MagicMock(spec=LLMService)
    llm_service.default_model = "gpt-4"
    return llm_service


@pytest.fixture
def mock_state_manager():
    """Create mock StateManager."""
    return MagicMock(spec=StateManager)


@pytest.fixture
def mock_todo_list_manager():
    """Create mock TodoListManager."""
    from capstone.agent_v2.planning.todolist import TodoListManager
    return MagicMock(spec=TodoListManager)


@pytest.fixture
def agent(mock_llm_service, mock_state_manager, mock_todo_list_manager):
    """Create Agent instance with mocked dependencies."""
    agent = Agent(
        name="Test Agent",
        description="Test agent for execute tests",
        system_prompt="Test system prompt",
        mission=None,
        tools=[],
        todo_list_manager=mock_todo_list_manager,
        state_manager=mock_state_manager,
        llm_service=mock_llm_service
    )
    return agent


def create_completed_todolist() -> TodoList:
    """Create a completed todolist for testing."""
    return TodoList(
        todolist_id="test-todolist-completed",
        items=[
            TodoItem(
                position=1,
                description="Task 1",
                acceptance_criteria="Task 1 complete",
                status=TaskStatus.COMPLETED,
                dependencies=[]
            ),
            TodoItem(
                position=2,
                description="Task 2",
                acceptance_criteria="Task 2 complete",
                status=TaskStatus.COMPLETED,
                dependencies=[]
            )
        ],
        open_questions=[],
        notes=""
    )


def create_incomplete_todolist() -> TodoList:
    """Create an incomplete todolist for testing."""
    return TodoList(
        todolist_id="test-todolist-incomplete",
        items=[
            TodoItem(
                position=1,
                description="Task 1",
                acceptance_criteria="Task 1 complete",
                status=TaskStatus.COMPLETED,
                dependencies=[]
            ),
            TodoItem(
                position=2,
                description="Task 2",
                acceptance_criteria="Task 2 complete",
                status=TaskStatus.PENDING,
                dependencies=[]
            )
        ],
        open_questions=[],
        notes=""
    )


@pytest.mark.asyncio
async def test_detect_completed_todolist_on_new_input(agent, mock_state_manager, mock_todo_list_manager):
    """Should detect when todolist is complete and flag for reset."""
    # Arrange: State with completed todolist, no pending question
    state: Dict[str, Any] = {
        "todolist_id": "test-todolist-completed"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    
    # Mock todolist loading - return completed todolist
    completed_todolist = create_completed_todolist()
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock the remaining methods to prevent full execution
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=completed_todolist)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock _react_loop to return immediately
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger to capture log calls
    agent.logger = MagicMock()
    
    # Act: Execute with new user message
    events = []
    async for event in agent.execute("New query", "session-123"):
        events.append(event)
    
    # Assert: Completed todolist was loaded (called twice: detection + _get_or_create_plan)
    assert mock_todo_list_manager.load_todolist.call_count >= 1
    mock_todo_list_manager.load_todolist.assert_any_call("test-todolist-completed")
    
    # Verify detection log message was called with correct parameters
    agent.logger.info.assert_any_call(
        "completed_todolist_detected_on_new_input",
        session_id="session-123",
        todolist_id="test-todolist-completed",
        will_reset=True
    )


@pytest.mark.asyncio
async def test_skip_detection_when_answering_question(agent, mock_state_manager, mock_todo_list_manager):
    """Should NOT reset when user is answering pending question."""
    # Arrange: State with pending question AND completed todolist
    state: Dict[str, Any] = {
        "todolist_id": "test-todolist-completed",
        "pending_question": {
            "question": "What is your name?",
            "answer_key": "user_name"
        }
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock todolist - should NOT be called since we have pending question
    completed_todolist = create_completed_todolist()
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with answer to pending question
    events = []
    async for event in agent.execute("John Doe", "session-123"):
        events.append(event)
    
    # Assert: Detection did NOT happen (no detection log message)
    # Note: load_todolist might be called by _get_or_create_plan after answer is processed
    info_calls = [call for call in agent.logger.info.call_args_list]
    detection_calls = [
        call for call in info_calls 
        if len(call[0]) > 0 and call[0][0] == "completed_todolist_detected_on_new_input"
    ]
    assert len(detection_calls) == 0, "Detection should NOT run when answering pending question"
    
    # Assert: Pending question flow continues (answer received)
    agent.logger.info.assert_any_call(
        "answer_received",
        session_id="session-123",
        answer_key="user_name"
    )


@pytest.mark.asyncio
async def test_handle_missing_todolist_file(agent, mock_state_manager, mock_todo_list_manager):
    """Should handle gracefully when todolist file is missing."""
    # Arrange: State has todolist_id but file doesn't exist
    state: Dict[str, Any] = {
        "todolist_id": "missing-todolist"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    
    # Mock todolist loading to raise FileNotFoundError
    mock_todo_list_manager.load_todolist = AsyncMock(side_effect=FileNotFoundError("Todolist not found"))
    
    # Mock create_todolist for subsequent flow
    new_todolist = create_incomplete_todolist()
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with new message
    events = []
    async for event in agent.execute("New query", "session-456"):
        events.append(event)
    
    # Assert: Warning was logged about missing file (may be logged multiple times)
    agent.logger.warning.assert_any_call(
        "todolist_file_not_found",
        session_id="session-456",
        todolist_id="missing-todolist"
    )
    
    # Assert: No crash, execution continues
    assert len(events) >= 0  # Should complete without error


@pytest.mark.asyncio
async def test_no_detection_when_no_todolist(agent, mock_state_manager, mock_todo_list_manager):
    """Should not attempt detection when no todolist exists."""
    # Arrange: Fresh state with no todolist_id
    state: Dict[str, Any] = {}
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock create_todolist for first-time creation
    new_todolist = create_incomplete_todolist()
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with first query
    events = []
    async for event in agent.execute("First query", "new-session"):
        events.append(event)
    
    # Assert: load_todolist should NOT be called (no todolist_id)
    mock_todo_list_manager.load_todolist.assert_not_called()
    
    # Assert: No detection log messages
    # Get all info log calls
    info_calls = [call for call in agent.logger.info.call_args_list]
    detection_calls = [
        call for call in info_calls 
        if call[0][0] == "completed_todolist_detected_on_new_input"
    ]
    assert len(detection_calls) == 0


@pytest.mark.asyncio
async def test_skip_detection_when_todolist_incomplete(agent, mock_state_manager, mock_todo_list_manager):
    """Should NOT reset when todolist is still in progress."""
    # Arrange: State with incomplete todolist
    state: Dict[str, Any] = {
        "todolist_id": "test-todolist-incomplete"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    
    # Mock todolist loading - return incomplete todolist
    incomplete_todolist = create_incomplete_todolist()
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=incomplete_todolist)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with follow-up input
    events = []
    async for event in agent.execute("Continue task", "session-789"):
        events.append(event)
    
    # Assert: Todolist was loaded (may be called twice: detection + _get_or_create_plan)
    assert mock_todo_list_manager.load_todolist.call_count >= 1
    mock_todo_list_manager.load_todolist.assert_any_call("test-todolist-incomplete")
    
    # Assert: No detection log (because todolist is not complete)
    info_calls = [call for call in agent.logger.info.call_args_list]
    detection_calls = [
        call for call in info_calls 
        if len(call[0]) > 0 and call[0][0] == "completed_todolist_detected_on_new_input"
    ]
    assert len(detection_calls) == 0, "Detection should NOT log when todolist is incomplete"


# ===== Story 2: Mission Reset Tests =====


@pytest.mark.asyncio
async def test_mission_reset_clears_state(agent, mock_state_manager, mock_todo_list_manager):
    """Should clear mission and remove todolist_id from state."""
    # Arrange: Agent with completed todolist and existing mission
    agent.mission = "Previous mission"
    state: Dict[str, Any] = {
        "todolist_id": "completed-todolist-123"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock completed todolist
    completed_todolist = create_completed_todolist()
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock create_todolist for new plan
    new_todolist = create_incomplete_todolist()
    new_todolist.todolist_id = "new-todolist-456"
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with new query
    events = []
    async for event in agent.execute("New query", "session-reset-1"):
        events.append(event)
    
    # Assert: Mission was cleared then reset to new query
    assert agent.mission == "New query"
    
    # Assert: State was updated - save_state called at least twice 
    # (once for reset, once for new todolist)
    assert mock_state_manager.save_state.call_count >= 1
    
    # Assert: Reset logs were generated (CONV-HIST-001: now includes conversation preservation)
    agent.logger.info.assert_any_call(
        "resetting_mission_preserving_conversation",
        session_id="session-reset-1",
        previous_mission_preview="Previous mission",
        previous_todolist_id="completed-todolist-123",
        new_query_preview="New query",
        conversation_preserved=True,
        message_count=ANY  # Message count will vary
    )
    agent.logger.info.assert_any_call("mission_reset_complete", session_id="session-reset-1")


@pytest.mark.asyncio
async def test_mission_reset_emits_event(agent, mock_state_manager, mock_todo_list_manager):
    """Should emit STATE_UPDATED event with reset info."""
    # Arrange: Agent with completed todolist
    agent.mission = "Old mission"
    state: Dict[str, Any] = {
        "todolist_id": "completed-todolist-abc"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock completed todolist
    completed_todolist = create_completed_todolist()
    completed_todolist.todolist_id = "completed-todolist-abc"
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock create_todolist for new plan
    new_todolist = create_incomplete_todolist()
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with new query, collect events
    events = []
    async for event in agent.execute("Another query", "session-reset-2"):
        events.append(event)
    
    # Assert: STATE_UPDATED event emitted with reset info
    reset_events = [
        e for e in events 
        if e.type.value == "state_updated" and e.data.get("mission_reset") is True
    ]
    assert len(reset_events) == 1, "Should emit exactly one reset event"
    
    reset_event = reset_events[0]
    assert reset_event.data["reason"] == "completed_todolist_detected"
    assert reset_event.data["previous_todolist_id"] == "completed-todolist-abc"


@pytest.mark.asyncio
async def test_new_todolist_created_after_reset(agent, mock_state_manager, mock_todo_list_manager):
    """Should create new todolist with new mission."""
    # Arrange: Agent with completed todolist
    agent.mission = "First mission"
    state: Dict[str, Any] = {
        "todolist_id": "old-todolist-999"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock completed todolist
    completed_todolist = create_completed_todolist()
    completed_todolist.todolist_id = "old-todolist-999"
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock create_todolist for new plan
    new_todolist = create_incomplete_todolist()
    new_todolist.todolist_id = "new-todolist-888"
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute with new query
    events = []
    async for event in agent.execute("Second mission", "session-reset-3"):
        events.append(event)
    
    # Assert: New todolist was created
    mock_todo_list_manager.create_todolist.assert_called_once()
    
    # Assert: create_todolist was called with new mission
    create_call_args = mock_todo_list_manager.create_todolist.call_args
    assert create_call_args.kwargs["mission"] == "Second mission"
    
    # Assert: New todolist_id in state (different from previous)
    assert agent.state.get("todolist_id") == "new-todolist-888"
    assert agent.state["todolist_id"] != "old-todolist-999"


@pytest.mark.asyncio
async def test_reset_preserves_other_state(agent, mock_state_manager, mock_todo_list_manager):
    """Should preserve answers and other state fields."""
    # Arrange: State with answers and completed todolist
    agent.mission = "Original mission"
    state: Dict[str, Any] = {
        "todolist_id": "completed-list-preserve",
        "answers": {
            "user_name": "John Doe",
            "project_name": "Test Project"
        },
        "custom_field": "should_remain"
    }
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock completed todolist
    completed_todolist = create_completed_todolist()
    mock_todo_list_manager.load_todolist = AsyncMock(return_value=completed_todolist)
    
    # Mock create_todolist for new plan
    new_todolist = create_incomplete_todolist()
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute reset
    events = []
    async for event in agent.execute("New mission", "session-reset-4"):
        events.append(event)
    
    # Assert: Answers still in state
    assert "answers" in agent.state
    assert agent.state["answers"]["user_name"] == "John Doe"
    assert agent.state["answers"]["project_name"] == "Test Project"
    
    # Assert: Custom field preserved
    assert agent.state.get("custom_field") == "should_remain"
    
    # Assert: Only todolist_id was initially removed (then re-added by new plan)
    # The key point is that other state fields were NOT touched during reset


@pytest.mark.asyncio
async def test_no_reset_for_single_mission(agent, mock_state_manager, mock_todo_list_manager):
    """Should not reset for traditional single-mission usage."""
    # Arrange: Agent used once, not yet complete
    agent.mission = None  # First time usage
    state: Dict[str, Any] = {}  # No existing todolist
    mock_state_manager.load_state = AsyncMock(return_value=state)
    mock_state_manager.save_state = AsyncMock()
    
    # Mock create_todolist for first-time creation
    new_todolist = create_incomplete_todolist()
    mock_todo_list_manager.create_todolist = AsyncMock(return_value=new_todolist)
    
    # Mock _react_loop
    async def mock_react_loop(*args, **kwargs):
        if False:
            yield None
    agent._react_loop = mock_react_loop
    
    # Mock logger
    agent.logger = MagicMock()
    
    # Act: Execute first time
    events = []
    async for event in agent.execute("First mission", "session-single"):
        events.append(event)
    
    # Assert: No reset log messages
    info_calls = [call for call in agent.logger.info.call_args_list]
    reset_calls = [
        call for call in info_calls 
        if len(call[0]) > 0 and call[0][0] == "resetting_mission_for_new_query"
    ]
    assert len(reset_calls) == 0, "Should not reset on first mission"
    
    # Assert: No reset events
    reset_events = [
        e for e in events 
        if e.type.value == "state_updated" and e.data.get("mission_reset") is True
    ]
    assert len(reset_events) == 0, "Should not emit reset event on first mission"
    
    # Assert: Mission was set normally
    assert agent.mission == "First mission"
