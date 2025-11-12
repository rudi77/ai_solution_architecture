"""
Integration tests for conversation history preservation across mission resets.

Story: CONV-HIST-001 - Remove MessageHistory Reset from Mission Reset
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from capstone.agent_v2.agent import Agent, AgentEventType
from capstone.agent_v2.planning.todolist import TodoList, TodoItem, TaskStatus
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tools.llm_tool import LLMTool


@pytest_asyncio.fixture
async def mock_llm_service():
    """Create a mock LLM service for testing."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock(return_value={
        "success": True,
        "content": "Test response"
    })
    return service


@pytest_asyncio.fixture
async def mock_state_manager():
    """Create a mock state manager for testing."""
    manager = MagicMock(spec=StateManager)
    manager.load_state = AsyncMock(return_value={})
    manager.save_state = AsyncMock()
    return manager


@pytest_asyncio.fixture
async def mock_todolist_manager():
    """Create a mock todo list manager for testing."""
    from capstone.agent_v2.planning.todolist import TodoListManager
    manager = MagicMock(spec=TodoListManager)
    
    # Return completed todolist on first call, then simulate new list
    completed_todo = TodoList(
        items=[
            TodoItem(
                position=1, 
                description="Task 1", 
                acceptance_criteria="Task completed",
                status=TaskStatus.COMPLETED
            )
        ],
        open_questions=[],
        notes="",
        todolist_id="test-todo-1"
    )
    
    manager.load_todolist = AsyncMock(return_value=completed_todo)
    manager.save_todolist = AsyncMock()
    manager.create_todolist = AsyncMock(return_value=TodoList(
        items=[],
        open_questions=[],
        notes="",
        todolist_id="test-todo-2"
    ))
    
    return manager


@pytest_asyncio.fixture
async def test_agent(mock_llm_service, mock_state_manager, mock_todolist_manager):
    """Create a test agent with mocked dependencies."""
    agent = Agent(
        name="TestAgent",
        description="Test agent for conversation history preservation",
        system_prompt="Test system prompt",
        mission="Initial mission",
        tools=[LLMTool("test-llm", mock_llm_service)],
        todo_list_manager=mock_todolist_manager,
        state_manager=mock_state_manager,
        llm_service=mock_llm_service
    )
    return agent


@pytest.mark.asyncio
async def test_message_history_grows_across_queries(test_agent):
    """Message history should accumulate across mission resets."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    initial_message_count = len(test_agent.message_history.messages)
    
    # Mock agent to stop after reset event
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Query 1: Execute with completed todolist (should trigger reset)
        events = []
        async for event in test_agent.execute("Query 1: Test question", "session-1"):
            events.append(event)
            # Stop after reset event
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Verify reset event was emitted with conversation info
        reset_events = [e for e in events if e.data.get("mission_reset")]
        assert len(reset_events) == 1
        assert reset_events[0].data["conversation_preserved"] is True
        assert "message_count" in reset_events[0].data
        
        # Add messages manually to simulate agent execution
        test_agent.message_history.add_message("Query 1: Test question", "user")
        test_agent.message_history.add_message("Response 1", "assistant")
        
        # Check message count increased
        after_query1_count = len(test_agent.message_history.messages)
        assert after_query1_count > initial_message_count
        
        # Query 2: Execute again (should trigger another reset)
        test_agent.state = {"todolist_id": "test-todo-2"}
        events2 = []
        async for event in test_agent.execute("Query 2: Different question", "session-1"):
            events2.append(event)
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Verify message count continues to increase
        after_query2_count = len(test_agent.message_history.messages)
        assert after_query2_count >= after_query1_count
        
        # Both queries should be visible in history
        messages_content = [m["content"] for m in test_agent.message_history.messages]
        assert any("Query 1" in str(m) for m in messages_content)


@pytest.mark.asyncio
async def test_todolist_resets_independently(test_agent):
    """TodoList should still reset while history preserved."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query that should trigger reset
        events = []
        async for event in test_agent.execute("New query", "session-1"):
            events.append(event)
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Verify reset occurred
        reset_events = [e for e in events if e.data.get("mission_reset")]
        assert len(reset_events) == 1
        assert reset_events[0].data["previous_todolist_id"] == "test-todo-1"
        
        # Verify todolist ID was removed from state
        assert "todolist_id" not in test_agent.state
        
        # Verify mission was cleared
        assert test_agent.mission is None or test_agent.mission == "New query"
        
        # Verify message history was NOT reset
        assert len(test_agent.message_history.messages) > 0


@pytest.mark.asyncio
async def test_conversation_preserved_in_reset_event(test_agent):
    """Reset event should include conversation preservation information."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Add some messages to history
    test_agent.message_history.add_message("Previous query", "user")
    test_agent.message_history.add_message("Previous response", "assistant")
    message_count_before = len(test_agent.message_history.messages)
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query that triggers reset
        events = []
        async for event in test_agent.execute("New query", "session-1"):
            events.append(event)
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Find reset event
        reset_events = [e for e in events if e.data.get("mission_reset")]
        assert len(reset_events) == 1
        
        reset_data = reset_events[0].data
        
        # Verify required fields
        assert reset_data["mission_reset"] is True
        assert reset_data["reason"] == "completed_todolist_detected"
        assert reset_data["conversation_preserved"] is True
        assert "message_count" in reset_data
        assert reset_data["message_count"] == message_count_before


@pytest.mark.asyncio
async def test_llm_sees_accumulated_context(test_agent):
    """LLM should see accumulated conversation history across resets."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Add first query to history
    test_agent.message_history.add_message("What is X?", "user")
    test_agent.message_history.add_message("X is a test", "assistant")
    
    call_count = 0
    captured_contexts = []
    
    async def mock_thought_capture(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Capture the context passed to LLM
        if hasattr(test_agent.message_history, 'messages'):
            captured_contexts.append(list(test_agent.message_history.messages))
        return {"action": {"type": "complete", "output": f"Response {call_count}"}}
    
    with patch.object(test_agent, '_generate_thought_with_context', side_effect=mock_thought_capture):
        # Execute second query (should trigger reset)
        events = []
        async for event in test_agent.execute("What about Y?", "session-1"):
            events.append(event)
            # Let it run through at least one thought generation
            if call_count >= 1:
                break
        
        # Verify history contains both queries context
        current_messages = test_agent.message_history.messages
        message_contents = [m["content"] for m in current_messages]
        
        # System prompt should still be first
        assert current_messages[0]["role"] == "system"
        
        # Previous conversation should be present
        assert any("X is a test" in str(content) for content in message_contents)


@pytest.mark.asyncio
async def test_no_message_history_reset_in_code(test_agent):
    """Verify MessageHistory is never reinitialized during reset."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Store reference to original message history object
    original_history_id = id(test_agent.message_history)
    
    # Add messages
    test_agent.message_history.add_message("Test query", "user")
    test_agent.message_history.add_message("Test response", "assistant")
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query that triggers reset
        async for event in test_agent.execute("New query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Verify message history object is the same instance (not recreated)
        current_history_id = id(test_agent.message_history)
        assert current_history_id == original_history_id, \
            "MessageHistory was recreated during reset (BUG!)"
        
        # Verify messages were preserved
        assert len(test_agent.message_history.messages) >= 3  # system + user + assistant


@pytest.mark.asyncio
async def test_logging_includes_conversation_metrics(test_agent, caplog):
    """Verify logging includes conversation preservation information."""
    import structlog
    from structlog.testing import CapturingLogger
    
    # Setup capturing logger
    capturing_logger = CapturingLogger()
    structlog.configure(
        processors=[],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=lambda: capturing_logger
    )
    
    # Recreate agent with new logger
    test_agent.logger = structlog.get_logger().bind(agent="TestAgent")
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Add some history
    test_agent.message_history.add_message("Query", "user")
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute to trigger reset
        async for event in test_agent.execute("New query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
    
    # Check captured logs
    log_entries = capturing_logger.calls
    
    # Find reset log
    reset_logs = [
        call for call in log_entries 
        if call.method_name == "info" and 
        "resetting_mission" in str(call.args) or 
        "conversation_preserved" in str(call.kwargs)
    ]
    
    # Should have logs about mission reset
    assert len(reset_logs) > 0 or any("mission_reset" in str(call) for call in log_entries)

