# Story 1: Remove MessageHistory Reset from Mission Reset

**Epic:** Conversation History Preservation - Brownfield Enhancement  
**Story ID:** CONV-HIST-001  
**Status:** Draft  
**Priority:** Critical  
**Estimated Effort:** 0.5 days  

## Story Description

Fix the critical bug where MessageHistory persists stale context across mission resets, causing the LLM to return cached answers from previous queries instead of processing new questions. This story removes the incorrect MessageHistory reset behavior to preserve conversation context while maintaining TodoList reset functionality.

## User Story

**As a** RAG CLI user  
**I want** each new question to receive a fresh, contextually appropriate answer  
**So that** I can ask multiple different questions in a single session without getting cached/stale responses

## Acceptance Criteria

### Functional Requirements

1. **Bug Fix: No MessageHistory Reset on Mission Reset**
   - [ ] Remove any MessageHistory reset/reinitialization in mission reset block (lines 409-444 in agent.py)
   - [ ] Verify MessageHistory is preserved when `should_reset_mission = True`
   - [ ] Ensure MessageHistory continues accumulating across mission boundaries
   - [ ] Confirm LLM sees full conversation history for new queries

2. **Preserve Existing Mission/TodoList Reset**
   - [ ] Mission reset still sets `self.mission = None` (line 420)
   - [ ] TodoList ID still removed from state (line 421)
   - [ ] State save still occurs after reset (line 425)
   - [ ] Reset event still emitted (lines 435-442)
   - [ ] All existing multi-turn behavior preserved from previous epic

3. **Conversation Context Verification**
   - [ ] First query: Agent processes and adds to history
   - [ ] Second query (different topic): Agent sees both queries in context
   - [ ] Second query: Agent generates NEW thought process (not "Step 3" continuation)
   - [ ] Second query: Agent returns appropriate answer for NEW query, not cached first answer
   - [ ] Message count increases naturally across queries

4. **Logging Enhancement**
   - [ ] Add message_count to mission reset log
   - [ ] Log that conversation history is being preserved
   - [ ] Use structured logging: `conversation_preserved=True, message_count=N`
   - [ ] Update reset event to include conversation preservation info

### Technical Requirements

1. **Code Location**
   - Modify: `capstone/agent_v2/agent.py`
   - Method: `Agent.execute()` mission reset block (lines 409-444)
   - Verify: No MessageHistory manipulation in reset block
   - Ensure: MessageHistory only touched in `__init__()` (line 348)

2. **Implementation Pattern**
   ```python
   # In mission reset block (lines 409-444):
   if should_reset_mission:
       self.logger.info(
           "resetting_mission_preserving_conversation",
           session_id=session_id,
           previous_mission_preview=self.mission[:100] if self.mission else None,
           previous_todolist_id=previous_todolist_id,
           new_query_preview=user_message[:100],
           # NEW: Log conversation preservation
           conversation_preserved=True,
           message_count=len(self.message_history.messages)
       )
       
       # Clear mission and todolist - but NOT message history
       self.mission = None
       self.state.pop("todolist_id", None)
       
       # ❌ DO NOT DO THIS (if it exists, remove it):
       # self.message_history = MessageHistory(...)  # BUG - DO NOT RESET!
       
       # Persist state changes (existing)
       await self.state_manager.save_state(session_id, self.state)
       
       # Notify CLI that reset occurred (existing, but enhance)
       yield AgentEvent(
           type=AgentEventType.STATE_UPDATED,
           data={
               "mission_reset": True,
               "reason": "completed_todolist_detected",
               "previous_todolist_id": previous_todolist_id,
               # NEW: Add conversation context info
               "conversation_preserved": True,
               "message_count": len(self.message_history.messages)
           }
       )
   ```

3. **Type Annotations**
   - [ ] No new variables introduced
   - [ ] Existing types remain unchanged
   - [ ] Event data dict properly typed

4. **Error Handling**
   - [ ] No new error cases introduced
   - [ ] Existing error handling preserved
   - [ ] Safe access to message_history.messages length

### Code Quality Requirements

1. **Python Best Practices**
   - [ ] PEP8 compliant formatting
   - [ ] Clear comments explaining "why conversation preserved"
   - [ ] No dead code (remove any MessageHistory reset if present)
   - [ ] Consistent with existing code style

2. **Logging Best Practices**
   - [ ] Use structlog with structured fields
   - [ ] Include conversation metrics (message_count)
   - [ ] No sensitive data in logs
   - [ ] Consistent log field naming

3. **Testing**
   - [ ] Integration test: Two different queries return different answers
   - [ ] Integration test: Second query sees first query in context
   - [ ] Integration test: Message history grows across queries
   - [ ] Integration test: TodoList still resets correctly
   - [ ] Manual test: Verify actual CLI behavior with example from epic

### Backward Compatibility

1. **Existing Flows Must Work**
   - [ ] Single-mission agents: No change (only execute once)
   - [ ] Multi-turn conversations: TodoList reset preserved
   - [ ] Pending questions: No interference
   - [ ] State persistence: No changes

2. **No API Changes**
   - [ ] `execute()` signature unchanged
   - [ ] `MessageHistory` interface unchanged
   - [ ] Event types unchanged
   - [ ] State structure unchanged

3. **Performance**
   - [ ] No additional API calls
   - [ ] No new file I/O
   - [ ] Minimal memory impact (natural history growth)

## Implementation Details

### File Changes

**File:** `capstone/agent_v2/agent.py`

**Location:** Lines 409-444 (mission reset block in Agent.execute)

**Changes:**
1. Search for any MessageHistory reset/reinitialization code
2. Remove it if present (bug fix)
3. Add conversation preservation logging
4. Enhance state update event with conversation info

### Code Structure - Before (Current Bug)

```python
# IF there's code like this anywhere in mission reset block, REMOVE IT:
if should_reset_mission:
    # ... existing reset logic ...
    
    # ❌ BUG - This causes the problem (if it exists):
    self.message_history = MessageHistory(
        build_system_prompt(self.system_prompt, None, self.tools_description),
        self.llm_service
    )
    # This resets history and causes LLM to lose context
```

### Code Structure - After (Fixed)

```python
if should_reset_mission:
    self.logger.info(
        "resetting_mission_preserving_conversation",  # Updated message
        session_id=session_id,
        previous_mission_preview=self.mission[:100] if self.mission else None,
        previous_todolist_id=previous_todolist_id,
        new_query_preview=user_message[:100],
        conversation_preserved=True,  # NEW
        message_count=len(self.message_history.messages)  # NEW
    )
    
    # Clear mission and todolist - conversation history untouched
    self.mission = None
    self.state.pop("todolist_id", None)
    
    # Persist state changes
    try:
        await self.state_manager.save_state(session_id, self.state)
    except Exception as e:
        self.logger.error(
            "state_save_failed_during_reset",
            session_id=session_id,
            error=str(e)
        )
    
    # Notify CLI with enhanced event
    yield AgentEvent(
        type=AgentEventType.STATE_UPDATED,
        data={
            "mission_reset": True,
            "reason": "completed_todolist_detected",
            "previous_todolist_id": previous_todolist_id,
            "conversation_preserved": True,  # NEW
            "message_count": len(self.message_history.messages)  # NEW
        }
    )
    
    self.logger.info("mission_reset_complete", session_id=session_id)
```

### Testing Strategy

**Integration Tests Location:** `tests/integration/test_conversation_history_preservation.py` (new file)

**Test Cases:**

1. **Test: Different Queries Get Different Answers**
   ```python
   async def test_different_queries_get_different_answers():
       """Second query should get appropriate answer, not cached first answer."""
       # Setup: RAG agent
       # Query 1: "Wie funktioniert der Plankalender?"
       # Verify: Gets answer about Plankalender
       # Query 2: "Gibt es verschiedene Arbeitszeitmodelle?"
       # Verify: Gets DIFFERENT answer about Arbeitszeitmodelle
       # Assert: Answers are different and contextually appropriate
   ```

2. **Test: Message History Grows Across Queries**
   ```python
   async def test_message_history_grows_across_queries():
       """Message history should accumulate across mission resets."""
       # Setup: RAG agent
       # Get initial message count
       # Query 1: Execute and complete
       # Check message count increased
       # Query 2: Execute (after reset)
       # Assert: Message count continues to increase
       # Assert: Both queries visible in history
   ```

3. **Test: TodoList Still Resets**
   ```python
   async def test_todolist_resets_independently():
       """TodoList should still reset while history preserved."""
       # Setup: RAG agent
       # Query 1: Execute and complete, get todolist_id_1
       # Query 2: Execute (should trigger reset)
       # Assert: New todolist created (different ID)
       # Assert: Old todolist_id removed from state
       # Assert: Message history preserved
   ```

4. **Test: LLM Sees Full Context**
   ```python
   async def test_llm_sees_full_conversation_context():
       """LLM should see both queries when processing second query."""
       # Setup: RAG agent with mock LLM
       # Query 1: "What is X?"
       # Query 2: "What about Y?"
       # Assert: LLM call for Query 2 includes Query 1 in context
       # Assert: Message history passed to LLM contains both queries
   ```

5. **Test: No Step Number Continuation Bug**
   ```python
   async def test_no_step_continuation_from_previous_query():
       """Second query should start fresh, not continue from Step 3."""
       # Setup: RAG agent
       # Query 1: Execute until completion (reaches some step N)
       # Query 2: Execute new query
       # Assert: First thought for Query 2 is "Step 1", not "Step N+1"
       # Assert: No reference to previous query in rationale
   ```

## Dependencies

**Depends On:**
- Multi-Turn Conversation Epic (Stories 1-2) - Mission/TodoList reset infrastructure

**Blocks:**
- Story 2: System Prompt Decoupling (architectural improvement)
- Story 3: Automatic Compression (optimization)

**Related Code:**
- `Agent.execute()` - Mission reset block (lines 409-444)
- `MessageHistory` class - Conversation management (lines 73-183)
- `_generate_thought_with_context()` - LLM context building (line 717)
- `build_system_prompt()` - System prompt construction

## Definition of Done

- [ ] Any MessageHistory reset code removed from mission reset block
- [ ] Conversation preservation logging added
- [ ] State update event enhanced with conversation info
- [ ] All 5 integration tests written and passing
- [ ] Manual testing shows second query gets appropriate answer (not cached)
- [ ] No regression in TodoList reset behavior
- [ ] No regression in single-mission agent behavior
- [ ] Code review completed
- [ ] PEP8 compliant
- [ ] Documentation updated (inline comments)

## Testing Checklist

- [ ] Integration test: Different queries get different answers
- [ ] Integration test: Message history grows across queries
- [ ] Integration test: TodoList still resets independently
- [ ] Integration test: LLM sees full conversation context
- [ ] Integration test: No step number continuation bug
- [ ] Manual test: Run example from epic (Plankalender → Arbeitszeitmodelle)
- [ ] Manual test: Verify logging shows message counts
- [ ] Manual test: Verify second query processes correctly

## Dev Notes

### Context from Architecture

**Testing Standards:**
- Location: `tests/integration/test_conversation_history_preservation.py`
- Use pytest with async support (@pytest.mark.asyncio)
- Mock external dependencies (LLM calls, file I/O)
- Test both happy path and edge cases
- Verify logging output in tests

**Relevant Source Tree:**
- `capstone/agent_v2/agent.py` - Main Agent class
  - Lines 73-183: MessageHistory class
  - Lines 348-351: MessageHistory initialization
  - Lines 355-513: Agent.execute() method
  - Lines 409-444: Mission reset block (target for fix)

**Integration Points:**
- Mission reset logic from multi-turn epic
- MessageHistory management
- State persistence
- Event emission to CLI

### Previous Story Notes

From Multi-Turn Epic Story 2:
- Mission reset working correctly (lines 409-444)
- TodoList removal working correctly
- State persistence working correctly
- Reset detection working correctly

**Critical**: This story ONLY fixes conversation context bug. All mission/TodoList reset behavior must be preserved exactly as-is.

### Testing

**Test Framework:** pytest with async support
**Test Location:** `tests/integration/test_conversation_history_preservation.py`
**Mocking Strategy:** Mock LLM service, use real MessageHistory
**Assertions:** Verify behavior and logging output

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-01-12 | 1.0 | Initial story creation | PM Agent |

## Dev Agent Record

_This section will be populated by the development agent during implementation._

### Agent Model Used

_To be filled by dev agent_

### Debug Log References

_To be filled by dev agent_

### Completion Notes

_To be filled by dev agent_

### File List

_To be filled by dev agent_

## QA Results

_This section will be populated by QA Agent after review._

## Notes

- **CRITICAL BUG FIX**: This story fixes the immediate user-facing bug
- **Surgical Change**: Remove incorrect reset, add logging - minimal surface area
- **High Impact**: Fixes broken multi-turn conversations
- **Low Risk**: Only removes buggy code, doesn't add complex logic
- **Quick Win**: Can be completed in half day
- **Prerequisite**: Must complete this before Stories 2-3 for architectural improvements

## Example Validation

**Test with this exact scenario from the bug report:**

```
Query 1: "Wie funktioniert der Plankalender?"
Expected: Detailed explanation about Plankalender
Actual After Fix: ✅ Detailed explanation about Plankalender

Query 2: "Gibt es verschiedene Arbeitszeitmodelle?"
Expected: NEW search and explanation about Arbeitszeitmodelle
Actual Before Fix: ❌ Same Plankalender explanation (BUG)
Actual After Fix: ✅ NEW explanation about Arbeitszeitmodelle

Query 3: "Wie hängen diese zusammen?"
Expected: Answer referencing both previous topics
Actual After Fix: ✅ Contextual answer using conversation history
```

This validates:
1. Each query gets fresh processing ✅
2. Answers are contextually appropriate ✅
3. Conversation history enables follow-ups ✅

