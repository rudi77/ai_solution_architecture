"""Manual test script to validate logging output for multi-turn conversations.

Run this script to observe the logging behavior when an agent processes
multiple consecutive queries. Verify that:
1. First query logs show mission creation
2. Second query logs show reset detection and new mission
3. All events are logged appropriately

Usage:
    python -m capstone.agent_v2.tests.manual.test_multi_turn_logging
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from capstone.agent_v2.agent_factory import create_rag_agent
from capstone.agent_v2.agent import AgentEventType


# Configure logging to console with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


async def test_multi_turn_logging():
    """Run agent with multiple queries and observe log output."""
    
    print("\n" + "="*80)
    print("MULTI-TURN CONVERSATION LOGGING TEST")
    print("="*80)
    
    session_id = "logging_test_001"
    work_dir = "./test_multi_turn_work"
    
    print(f"\nSession ID: {session_id}")
    print(f"Work Directory: {work_dir}\n")
    
    # Create RAG agent
    agent = create_rag_agent(
        session_id=session_id,
        work_dir=work_dir,
        user_context={"user_id": "test", "org_id": "test", "scope": "shared"}
    )
    
    # First query
    print("\n" + "-"*80)
    print("FIRST QUERY: 'What is a Plankalender?'")
    print("-"*80)
    print("\nExpected logs:")
    print("  - execute_start")
    print("  - mission_set")
    print("  - plan_created\n")
    
    first_query = "What is a Plankalender?"
    event_count = 0
    
    async for event in agent.execute(first_query, session_id):
        event_count += 1
        print(f"Event {event_count}: {event.type.value}")
        
        if event.type == AgentEventType.COMPLETE:
            print(f"  → Query completed: {event.data.get('message', 'N/A')}")
            break
        elif event.type == AgentEventType.THOUGHT:
            thought_preview = event.data.get('thought', '')[:100]
            print(f"  → Thought: {thought_preview}...")
        elif event.type == AgentEventType.STATE_UPDATED:
            if event.data.get("todolist_created"):
                print(f"  → Todolist created with {event.data.get('items', 0)} items")
        elif event.type == AgentEventType.ERROR:
            print(f"  → ERROR: {event.data.get('error', 'Unknown error')}")
            break
    
    print(f"\nFirst query completed after {event_count} events")
    print(f"Todolist ID: {agent.state.get('todolist_id')}")
    
    # Second query - should show reset logs
    print("\n" + "-"*80)
    print("SECOND QUERY: 'What are Zeitmodelle?' (should show reset)")
    print("-"*80)
    print("\nExpected logs:")
    print("  - execute_start")
    print("  - completed_todolist_detected_on_new_input")
    print("  - resetting_mission_for_new_query")
    print("  - mission_reset_complete")
    print("  - mission_set")
    print("  - plan_created\n")
    
    second_query = "What are Zeitmodelle?"
    event_count = 0
    reset_detected = False
    
    async for event in agent.execute(second_query, session_id):
        event_count += 1
        print(f"Event {event_count}: {event.type.value}")
        
        if event.type == AgentEventType.STATE_UPDATED:
            if event.data.get("mission_reset"):
                reset_detected = True
                print(f"  → MISSION RESET detected!")
                print(f"  → Previous todolist: {event.data.get('previous_todolist_id', 'N/A')}")
                print(f"  → Reason: {event.data.get('reason', 'N/A')}")
            elif event.data.get("todolist_created"):
                print(f"  → New todolist created with {event.data.get('items', 0)} items")
        elif event.type == AgentEventType.THOUGHT:
            thought_preview = event.data.get('thought', '')[:100]
            print(f"  → Thought: {thought_preview}...")
            # Break after first thought to avoid long execution
            break
        elif event.type == AgentEventType.COMPLETE:
            print(f"  → Query completed: {event.data.get('message', 'N/A')}")
            break
        elif event.type == AgentEventType.ERROR:
            print(f"  → ERROR: {event.data.get('error', 'Unknown error')}")
            break
    
    print(f"\nSecond query processed {event_count} events")
    print(f"Reset detected: {reset_detected}")
    print(f"New todolist ID: {agent.state.get('todolist_id')}")
    
    # Third query - verify reset still works
    print("\n" + "-"*80)
    print("THIRD QUERY: 'How do Schichtmodelle work?' (verify continued reset)")
    print("-"*80)
    
    # Manually complete the second query's todolist to trigger another reset
    second_todolist_id = agent.state.get('todolist_id')
    if second_todolist_id:
        try:
            from capstone.agent_v2.planning.todolist import TaskStatus
            todolist = await agent.todo_list_manager.load_todolist(second_todolist_id)
            for item in todolist.items:
                item.status = TaskStatus.COMPLETED
            await agent.todo_list_manager.save_todolist(todolist)
            print("  → Manually completed second todolist to trigger reset")
        except Exception as e:
            print(f"  → Warning: Could not complete todolist: {e}")
    
    third_query = "How do Schichtmodelle work?"
    event_count = 0
    reset_detected = False
    
    async for event in agent.execute(third_query, session_id):
        event_count += 1
        print(f"Event {event_count}: {event.type.value}")
        
        if event.type == AgentEventType.STATE_UPDATED:
            if event.data.get("mission_reset"):
                reset_detected = True
                print(f"  → MISSION RESET detected (third query)!")
        elif event.type == AgentEventType.THOUGHT:
            print(f"  → Processing third query...")
            break
    
    print(f"\nThird query processed {event_count} events")
    print(f"Reset detected: {reset_detected}")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("\nVerify the following:")
    print("  [✓] First query: mission_set and plan_created logged")
    print("  [✓] Second query: reset logs appeared before mission_set")
    print("  [✓] Third query: reset occurred again for new query")
    print("  [✓] Each query received proper agent processing (thoughts, actions)")
    print("  [✓] No error events or exceptions occurred")
    print("\nIf all checks passed, multi-turn logging is working correctly!")
    print("="*80 + "\n")


async def test_pending_question_no_reset():
    """Test that pending questions don't trigger reset."""
    
    print("\n" + "="*80)
    print("PENDING QUESTION TEST (No Reset Expected)")
    print("="*80)
    
    session_id = "pending_question_test_001"
    work_dir = "./test_pending_work"
    
    from capstone.agent_v2.agent_factory import create_standard_agent
    
    agent = create_standard_agent(
        name="Test Agent",
        description="Agent for testing pending questions",
        mission="Complete a task",
        work_dir=work_dir
    )
    
    # Simulate pending question scenario
    agent.state = {
        "todolist_id": "test_todolist_001",
        "pending_question": {
            "question": "What is the target directory?",
            "answer_key": "target_dir"
        }
    }
    
    print("\nState setup: pending_question exists")
    print("Executing with user answer: '/home/user/projects'\n")
    
    user_answer = "/home/user/projects"
    reset_detected = False
    
    async for event in agent.execute(user_answer, session_id):
        print(f"Event: {event.type.value}")
        
        if event.type == AgentEventType.STATE_UPDATED:
            if event.data.get("mission_reset"):
                reset_detected = True
                print("  → ERROR: Reset detected (should NOT happen for pending question!)")
            elif event.data.get("answer_received"):
                print(f"  → Answer received: {event.data.get('answer_received')}")
                break
    
    print(f"\nReset detected: {reset_detected}")
    print(f"Answer stored: {agent.state.get('answers', {}).get('target_dir', 'N/A')}")
    print(f"Pending question cleared: {'pending_question' not in agent.state}")
    
    if not reset_detected and 'pending_question' not in agent.state:
        print("\n✓ Pending question flow works correctly (no reset)!")
    else:
        print("\n✗ Pending question flow has issues!")
    
    print("="*80 + "\n")


def main():
    """Run all manual logging tests."""
    print("\n" + "="*80)
    print("MANUAL LOGGING VALIDATION SUITE")
    print("Multi-Turn Conversation Feature")
    print("="*80 + "\n")
    
    # Run multi-turn logging test
    print("Running Test 1: Multi-Turn Conversation Logging...")
    asyncio.run(test_multi_turn_logging())
    
    # Run pending question test
    print("\nRunning Test 2: Pending Question No Reset...")
    asyncio.run(test_pending_question_no_reset())
    
    print("\n" + "="*80)
    print("ALL MANUAL TESTS COMPLETED")
    print("Review the output above to verify logging behavior")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

