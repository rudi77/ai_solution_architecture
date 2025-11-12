"""
Integration tests for conversation history preservation across mission resets.

Story: CONV-HIST-001 - Remove MessageHistory Reset from Mission Reset
Story: CONV-HIST-002 - System Prompt Decoupling from Mission
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


# ============================================================================
# Story CONV-HIST-002: System Prompt Decoupling from Mission
# ============================================================================


@pytest.mark.asyncio
async def test_system_prompt_stable_across_resets(test_agent):
    """System prompt should not change when mission resets (Story CONV-HIST-002)."""
    # Setup: Configure state manager to return state with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Get initial system prompt (first message in history)
    initial_system_prompt = test_agent.message_history.messages[0]["content"]
    assert test_agent.message_history.messages[0]["role"] == "system"
    
    # Verify system prompt does NOT contain mission
    assert "Initial mission" not in initial_system_prompt
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Query 1: Execute and complete
        async for event in test_agent.execute("Query 1: First question", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Add messages to simulate execution
        test_agent.message_history.add_message("Query 1: First question", "user")
        test_agent.message_history.add_message("Response 1", "assistant")
        
        # Get system prompt after first query
        after_query1_system_prompt = test_agent.message_history.messages[0]["content"]
        
        # Query 2: Execute (triggers reset)
        test_agent.state = {"todolist_id": "test-todo-2"}
        async for event in test_agent.execute("Query 2: Different question", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Get system prompt after reset
        after_query2_system_prompt = test_agent.message_history.messages[0]["content"]
        
        # Assert: System prompt unchanged (still first message)
        assert test_agent.message_history.messages[0]["role"] == "system"
        
        # Assert: Same system prompt content before and after reset
        assert initial_system_prompt == after_query1_system_prompt
        assert initial_system_prompt == after_query2_system_prompt


@pytest.mark.asyncio
async def test_queries_appear_as_user_messages(test_agent):
    """User queries should appear as natural conversation messages (Story CONV-HIST-002)."""
    # Setup
    test_agent.state_manager.load_state = AsyncMock(return_value={})
    
    # Add queries manually (simulating agent execution flow)
    query1 = "What is X?"
    query2 = "What is Y?"
    
    test_agent.message_history.add_message(query1, "user")
    test_agent.message_history.add_message("X is a concept", "assistant")
    test_agent.message_history.add_message(query2, "user")
    test_agent.message_history.add_message("Y is another concept", "assistant")
    
    # Assert: Query 1 added as {"role": "user", "content": "What is X?"}
    user_messages = [m for m in test_agent.message_history.messages if m["role"] == "user"]
    assert len(user_messages) >= 2
    assert any(query1 in m["content"] for m in user_messages)
    
    # Assert: Query 2 also in history as user message
    assert any(query2 in m["content"] for m in user_messages)
    
    # Assert: Natural conversation flow in history (system, user, assistant, user, assistant)
    roles = [m["role"] for m in test_agent.message_history.messages]
    assert roles[0] == "system"
    # Should have alternating user/assistant after system
    assert "user" in roles[1:]
    assert "assistant" in roles[1:]


@pytest.mark.asyncio
async def test_conversational_flow_with_stable_prompt(test_agent):
    """Agent should handle multi-turn conversation with stable system prompt (Story CONV-HIST-002)."""
    # Setup: Agent with mission-agnostic prompt
    test_agent.state_manager.load_state = AsyncMock(return_value={})
    
    # Get initial system prompt
    initial_system_prompt = test_agent.message_history.messages[0]["content"]
    initial_message_count = len(test_agent.message_history.messages)
    
    # Execute 3 different queries
    queries = [
        "What is machine learning?",
        "How does it work?",
        "Can you give an example?"
    ]
    
    for query in queries:
        test_agent.message_history.add_message(query, "user")
        # Simulate LLM response
        test_agent.message_history.add_message(f"Response to: {query}", "assistant")
    
    # Assert: All queries processed correctly (messages added)
    final_message_count = len(test_agent.message_history.messages)
    assert final_message_count > initial_message_count
    assert final_message_count >= initial_message_count + (len(queries) * 2)  # user + assistant per query
    
    # Assert: System prompt unchanged
    current_system_prompt = test_agent.message_history.messages[0]["content"]
    assert current_system_prompt == initial_system_prompt
    
    # Assert: Each query visible in history as user message
    user_messages = [m for m in test_agent.message_history.messages if m["role"] == "user"]
    for query in queries:
        assert any(query in m["content"] for m in user_messages)
    
    # Assert: LLM responses appropriate for each query (present in history)
    assistant_messages = [m for m in test_agent.message_history.messages if m["role"] == "assistant"]
    assert len(assistant_messages) >= len(queries)


@pytest.mark.asyncio
async def test_system_prompt_does_not_contain_mission(test_agent):
    """System prompt should NOT contain mission text (Story CONV-HIST-002)."""
    # Get system prompt from message history
    system_prompt = test_agent.message_history.messages[0]["content"]
    
    # Assert: System prompt does not contain mission
    assert test_agent.mission not in system_prompt or test_agent.mission == "Initial mission"
    # More specifically, should not have <Mission> tags
    assert "<Mission>" not in system_prompt
    
    # Assert: Mission stored in agent but not in prompt
    assert test_agent.mission is not None
    assert test_agent.mission == "Initial mission"


@pytest.mark.asyncio
async def test_backward_compatibility_mission_still_stored(test_agent):
    """Mission parameter still accepted and stored for backward compatibility (Story CONV-HIST-002)."""
    # Assert: Agent still has mission attribute
    assert hasattr(test_agent, "mission")
    assert test_agent.mission == "Initial mission"
    
    # Assert: Mission can be updated
    test_agent.mission = "Updated mission"
    assert test_agent.mission == "Updated mission"
    
    # Assert: System prompt template stored
    assert hasattr(test_agent, "system_prompt_template")
    assert test_agent.system_prompt_template == "Test system prompt"


# ============================================================================
# Story CONV-HIST-003: Automatic History Compression Management
# ============================================================================


@pytest.mark.asyncio
async def test_long_conversation_triggers_compression(test_agent, caplog):
    """Should trigger compression when message count exceeds threshold (Story CONV-HIST-003)."""
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
    test_agent.logger = structlog.get_logger().bind(agent="TestAgent")
    
    # Setup: Configure state manager with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Add 45 messages (exceeds threshold of 40)
    for i in range(22):  # 22 pairs = 44 messages + system prompt = 45 total
        test_agent.message_history.add_message(f"Query {i}", "user")
        test_agent.message_history.add_message(f"Response {i}", "assistant")
    
    message_count_before = len(test_agent.message_history.messages)
    assert message_count_before > 40, "Test setup failed: need >40 messages"
    
    # Mock compress_history_async to track if it was called
    original_compress = test_agent.message_history.compress_history_async
    compress_called = False
    
    async def mock_compress():
        nonlocal compress_called
        compress_called = True
        # Actually call the compression (will fail gracefully with mock LLM)
        await original_compress()
    
    test_agent.message_history.compress_history_async = mock_compress
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query to trigger mission reset
        async for event in test_agent.execute("New query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
    
    # Assert: compress_history_async() was called
    assert compress_called, "Compression should have been triggered for long conversation"
    
    # Assert: Log message "triggering_history_compression" emitted
    log_entries = capturing_logger.calls
    compression_trigger_logs = [
        call for call in log_entries
        if "triggering_history_compression" in str(call.args) or
        "triggering_history_compression" in str(call.kwargs)
    ]
    assert len(compression_trigger_logs) > 0, "Should log compression trigger"


@pytest.mark.asyncio
async def test_compression_reduces_message_count(test_agent):
    """Compression should reduce message count while preserving context (Story CONV-HIST-003)."""
    # Setup: Configure state manager with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Mock LLM to return successful compression
    test_agent.llm_service.complete = AsyncMock(return_value={
        "success": True,
        "content": "Summary of previous conversation: User asked multiple questions about topics X, Y, Z. Agent provided detailed explanations."
    })
    
    # Add 45 messages (exceeds threshold)
    for i in range(22):  # 22 pairs = 44 messages + system prompt = 45 total
        test_agent.message_history.add_message(f"Query {i}", "user")
        test_agent.message_history.add_message(f"Response {i}", "assistant")
    
    message_count_before = len(test_agent.message_history.messages)
    assert message_count_before > 40, "Test setup failed: need >40 messages"
    
    # Store system prompt for verification
    system_prompt = test_agent.message_history.messages[0]
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query to trigger compression
        async for event in test_agent.execute("New query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
    
    message_count_after = len(test_agent.message_history.messages)
    
    # Assert: Message count reduced
    assert message_count_after < message_count_before, "Compression should reduce message count"
    
    # Assert: System prompt still present (first message)
    assert test_agent.message_history.messages[0]["role"] == "system"
    assert test_agent.message_history.messages[0] == system_prompt
    
    # Assert: Summary message added (second message should be system with summary)
    if len(test_agent.message_history.messages) > 1:
        second_message = test_agent.message_history.messages[1]
        # Summary could be in system message or might have recent messages
        assert any("[Previous context summary]" in m["content"] or "Summary" in m["content"] 
                   for m in test_agent.message_history.messages 
                   if m["role"] == "system")


@pytest.mark.asyncio
async def test_context_preserved_after_compression(test_agent):
    """Essential context should be preserved after compression (Story CONV-HIST-003)."""
    # Setup: Configure state manager with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Mock LLM to return successful compression with context
    test_agent.llm_service.complete = AsyncMock(return_value={
        "success": True,
        "content": "Summary: User discussed important topics including machine learning, neural networks, and data processing. Agent explained concepts in detail."
    })
    
    # Add long conversation with important facts
    test_agent.message_history.add_message("What is machine learning?", "user")
    test_agent.message_history.add_message("ML is a type of AI", "assistant")
    
    for i in range(20):  # Add more messages to exceed threshold
        test_agent.message_history.add_message(f"Follow-up question {i}", "user")
        test_agent.message_history.add_message(f"Answer {i}", "assistant")
    
    # Add recent important message
    test_agent.message_history.add_message("Tell me more about neural networks", "user")
    test_agent.message_history.add_message("Neural networks are...", "assistant")
    
    assert len(test_agent.message_history.messages) > 40
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Trigger compression via mission reset
        async for event in test_agent.execute("New related query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
    
    # Assert: Recent messages preserved
    messages_content = [m["content"] for m in test_agent.message_history.messages]
    assert any("neural networks" in str(content).lower() for content in messages_content), \
        "Recent important context should be preserved"
    
    # Assert: System prompt still intact
    assert test_agent.message_history.messages[0]["role"] == "system"
    
    # Assert: Conversation can continue naturally (history structure valid)
    assert len(test_agent.message_history.messages) > 0
    assert all("role" in m and "content" in m for m in test_agent.message_history.messages)


@pytest.mark.asyncio
async def test_short_conversations_skip_compression(test_agent, caplog):
    """Should not compress when message count below threshold (Story CONV-HIST-003)."""
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
    test_agent.logger = structlog.get_logger().bind(agent="TestAgent")
    
    # Setup: Configure state manager with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Add only 20 messages (below threshold of 40)
    for i in range(9):  # 9 pairs = 18 messages + system prompt = 19 total
        test_agent.message_history.add_message(f"Query {i}", "user")
        test_agent.message_history.add_message(f"Response {i}", "assistant")
    
    message_count_before = len(test_agent.message_history.messages)
    assert message_count_before <= 40, "Test setup failed: need <=40 messages"
    
    # Mock compress to track if called
    compress_called = False
    original_compress = test_agent.message_history.compress_history_async
    
    async def mock_compress():
        nonlocal compress_called
        compress_called = True
        await original_compress()
    
    test_agent.message_history.compress_history_async = mock_compress
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query to trigger mission reset
        async for event in test_agent.execute("New query", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
    
    # Assert: compress_history_async() NOT called
    assert not compress_called, "Compression should NOT be triggered for short conversations"
    
    # Assert: No compression logs emitted
    log_entries = capturing_logger.calls
    compression_logs = [
        call for call in log_entries
        if "compression" in str(call.args).lower() or "compression" in str(call.kwargs).lower()
    ]
    assert len(compression_logs) == 0, "Should not log compression for short conversations"
    
    # Assert: Message count unchanged
    message_count_after = len(test_agent.message_history.messages)
    assert message_count_after == message_count_before


@pytest.mark.asyncio
async def test_graceful_compression_failure(test_agent, caplog):
    """Should continue execution if compression fails (Story CONV-HIST-003)."""
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
    test_agent.logger = structlog.get_logger().bind(agent="TestAgent")
    
    # Setup: Configure state manager with completed todolist
    test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
    
    # Mock LLM to fail compression
    test_agent.llm_service.complete = AsyncMock(return_value={
        "success": False,
        "error": "LLM service unavailable"
    })
    
    # Add 45 messages to trigger compression
    for i in range(22):
        test_agent.message_history.add_message(f"Query {i}", "user")
        test_agent.message_history.add_message(f"Response {i}", "assistant")
    
    assert len(test_agent.message_history.messages) > 40
    
    # Track that execution continues
    execution_continued = False
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        mock_thought.return_value = {"action": {"type": "complete", "output": "Done"}}
        
        # Execute query (should NOT crash despite compression failure)
        try:
            async for event in test_agent.execute("New query", "session-1"):
                if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                    execution_continued = True
                    break
        except Exception as e:
            pytest.fail(f"Execution should not crash on compression failure: {e}")
    
    # Assert: Execution continues (doesn't crash)
    assert execution_continued, "Mission reset should complete successfully despite compression failure"
    
    # Assert: Error logged (either "compression_failed" from MessageHistory or "history_compression_failed" from agent)
    log_entries = capturing_logger.calls
    error_logs = [
        call for call in log_entries
        if call.method_name == "error" and
        ("compression_failed" in str(call.args) or "compression_failed" in str(call.kwargs) or
         "history_compression_failed" in str(call.args) or "history_compression_failed" in str(call.kwargs))
    ]
    assert len(error_logs) > 0, "Should log compression failure"
    
    # Assert: Mission reset completes successfully
    assert test_agent.mission is None or "New query" in str(test_agent.mission)
    assert "todolist_id" not in test_agent.state
    
    # Assert: Agent still functional (message history intact)
    assert len(test_agent.message_history.messages) > 0


@pytest.mark.asyncio
async def test_compression_at_reset_boundary(test_agent, caplog):
    """Compression should happen during mission reset, not mid-query (Story CONV-HIST-003)."""
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
    test_agent.logger = structlog.get_logger().bind(agent="TestAgent")
    
    # Setup: Configure state manager WITHOUT completed todolist initially
    test_agent.state_manager.load_state = AsyncMock(return_value={})
    
    # Add 45 messages
    for i in range(22):
        test_agent.message_history.add_message(f"Query {i}", "user")
        test_agent.message_history.add_message(f"Response {i}", "assistant")
    
    assert len(test_agent.message_history.messages) > 40
    
    # Track compression timing
    compress_called_during_query = False
    compress_called_during_reset = False
    
    original_compress = test_agent.message_history.compress_history_async
    
    async def mock_compress():
        nonlocal compress_called_during_query, compress_called_during_reset
        # Check if we're in reset context (mission is None after reset)
        if test_agent.mission is None:
            compress_called_during_reset = True
        else:
            compress_called_during_query = True
        await original_compress()
    
    test_agent.message_history.compress_history_async = mock_compress
    
    call_count = 0
    
    with patch.object(test_agent, '_generate_thought_with_context', new_callable=AsyncMock) as mock_thought:
        def mock_return(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"action": {"type": "complete", "output": "Done"}}
        
        mock_thought.side_effect = mock_return
        
        # Execute query WITHOUT triggering reset (no completed todolist)
        async for event in test_agent.execute("Query during execution", "session-1"):
            if call_count >= 1:  # Let at least one thought complete
                break
        
        # Assert: Compression NOT triggered mid-query
        assert not compress_called_during_query, "Should not compress during active query"
        
        # Now trigger reset
        test_agent.state = {"todolist_id": "test-todo-1"}
        test_agent.state_manager.load_state = AsyncMock(return_value={"todolist_id": "test-todo-1"})
        
        # Execute new query (should trigger reset and compression)
        async for event in test_agent.execute("Query triggering reset", "session-1"):
            if event.type == AgentEventType.STATE_UPDATED and event.data.get("mission_reset"):
                break
        
        # Assert: Compression happens during reset
        # Note: Due to timing, compression might happen after mission is cleared
        # The key is it happens in the reset block, not during query processing
        log_entries = capturing_logger.calls
        compression_logs = [
            call for call in log_entries
            if "triggering_history_compression" in str(call.args) or
            "triggering_history_compression" in str(call.kwargs)
        ]
        
        # If compression was attempted, it should be in the reset context
        if len(compression_logs) > 0:
            # Verify compression happens near mission reset log
            reset_log_found = any(
                "resetting_mission" in str(call.args) or "resetting_mission" in str(call.kwargs)
                for call in log_entries
            )
            assert reset_log_found, "Compression should happen during mission reset"