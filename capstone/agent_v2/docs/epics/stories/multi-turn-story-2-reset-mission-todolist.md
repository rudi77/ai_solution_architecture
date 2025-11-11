# Story 2: Reset Mission and Create Fresh Todolist

**Epic:** Multi-Turn Conversation Support - Brownfield Enhancement  
**Story ID:** MULTI-TURN-002  
**Status:** Pending  
**Priority:** High  
**Estimated Effort:** 1 day  

## Story Description

Implement the mission reset logic that clears the completed mission and removes the todolist reference from state when a completed todolist is detected on new user input. This enables the agent to create a fresh todolist for the new query using the existing planning flow.

## User Story

**As a** RAG CLI user  
**I want** the agent to reset its mission after completing my previous query  
**So that** my new question is treated as a fresh task and gets full agent processing

## Acceptance Criteria

### Functional Requirements

1. **Mission Reset Logic**
   - [x] Add reset block after detection logic (from Story 1)
   - [x] Execute reset only when `should_reset_mission` is True
   - [x] Clear mission: `self.mission = None`
   - [x] Remove todolist reference: `self.state.pop("todolist_id", None)`
   - [x] Preserve other state fields (answers, etc.)

2. **State Persistence**
   - [x] Save updated state after reset
   - [x] Use existing `StateManager.save_state()` method
   - [x] Maintain session_id (same session continues)
   - [x] State file format unchanged

3. **Event Emission**
   - [x] Emit `AgentEvent` of type `STATE_UPDATED` after reset
   - [x] Include reset information in event data
   - [x] Follow existing event emission patterns
   - [x] Event data structure:
     ```python
     {
         "mission_reset": True,
         "reason": "completed_todolist_detected",
         "previous_todolist_id": <old_id>
     }
     ```

4. **New Todolist Creation**
   - [x] Verify existing `_get_or_create_plan()` handles reset correctly
   - [x] New todolist created with new user_message as mission
   - [x] New todolist_id assigned and saved to state
   - [x] No modification to todolist creation logic needed (uses existing flow)

5. **Logging**
   - [x] Log mission reset with context
   - [x] Log previous mission (preview, not full text)
   - [x] Log previous todolist_id
   - [x] Log new mission assignment
   - [x] Use structlog with session_id binding

### Technical Requirements

1. **Code Location**
   - Modify: `capstone/agent_v2/agent.py`
   - Method: `Agent.execute()` (starting at line 355)
   - Insert reset logic after detection block (from Story 1)
   - Before mission initialization block (line 376)

2. **Implementation Pattern**
   ```python
   # Pseudo-code structure:
   async def execute(self, user_message: str, session_id: str):
       # 1. Load state (existing)
       self.state = await self.state_manager.load_state(session_id)
       
       # 2. Detection logic (from Story 1)
       should_reset_mission = False
       previous_todolist_id = None
       
       if not self.state.get("pending_question"):
           todolist_id = self.state.get("todolist_id")
           if todolist_id:
               try:
                   existing_todolist = await self.todo_list_manager.load_todolist(todolist_id)
                   if self._is_plan_complete(existing_todolist):
                       should_reset_mission = True
                       previous_todolist_id = todolist_id
                       self.logger.info("completed_todolist_detected", ...)
               except FileNotFoundError:
                   pass
       
       # 3. NEW: Execute mission reset if needed
       if should_reset_mission:
           self.logger.info(
               "resetting_mission_for_new_query",
               session_id=session_id,
               previous_mission_preview=self.mission[:100] if self.mission else None,
               previous_todolist_id=previous_todolist_id
           )
           
           # Clear mission and todolist reference
           self.mission = None
           self.state.pop("todolist_id", None)
           
           # Save updated state
           await self.state_manager.save_state(session_id, self.state)
           
           # Emit state update event
           yield AgentEvent(
               type=AgentEventType.STATE_UPDATED,
               data={
                   "mission_reset": True,
                   "reason": "completed_todolist_detected",
                   "previous_todolist_id": previous_todolist_id
               }
           )
           
           self.logger.info("mission_reset_complete", session_id=session_id)
       
       # 4. Mission setzen (existing logic, now handles reset case)
       if self.mission is None:
           self.mission = user_message
           self.logger.info("mission_set", ...)
       
       # 5. Rest of execute() continues unchanged...
   ```

3. **Type Annotations**
   - [x] `previous_todolist_id: Optional[str]`
   - [x] Use `AgentEventType.STATE_UPDATED` enum
   - [x] Event data typed as `Dict[str, Any]`

4. **Error Handling**
   - [x] Wrap state save in try/except
   - [x] Log errors during reset
   - [x] Fail gracefully if state save fails
   - [x] Don't block execution if event emission fails

### Code Quality Requirements

1. **Python Best Practices**
   - [x] PEP8 compliant formatting
   - [x] Type annotations on all variables
   - [x] Clear variable names
   - [x] Comments explaining reset rationale
   - [x] Docstring update for `execute()` method

2. **Logging Best Practices**
   - [x] Use structlog with appropriate log levels
   - [x] Include context: session_id, previous_mission_preview, previous_todolist_id
   - [x] Log before and after reset (mission_resetting, mission_reset_complete)
   - [x] No full mission text in logs (privacy/size concerns)
   - [x] Structured log fields

3. **Event Emission**
   - [x] Follow existing AgentEvent patterns
   - [x] Use correct AgentEventType enum value
   - [x] Include meaningful data for CLI display
   - [x] Document event structure in code comments

### Backward Compatibility

1. **Existing Flows Must Work**
   - [x] Single-mission agents: Reset never triggers (no completed todolist)
   - [x] Pending questions: Reset skipped (detection prevented)
   - [x] First query: No reset (no todolist exists)
   - [x] In-progress missions: No reset (todolist not complete)

2. **No API Changes**
   - [x] `execute()` signature unchanged
   - [x] Return type unchanged (AsyncIterator[AgentEvent])
   - [x] New event type uses existing STATE_UPDATED enum value

3. **State Compatibility**
   - [x] Only removes todolist_id field (optional field)
   - [x] Other state fields preserved (answers, etc.)
   - [x] State file format unchanged
   - [x] Old state files compatible

## Implementation Details

### File Changes

**File:** `capstone/agent_v2/agent.py`

**Location:** Lines 355-404 (Agent.execute method)

**Changes:**
1. After detection block (from Story 1), add reset block
2. Clear mission and remove todolist_id from state
3. Save state and emit event
4. Let existing logic handle new mission and todolist creation

### Code Structure

```python
async def execute(self, user_message: str, session_id: str) -> AsyncIterator[AgentEvent]:
    """
    Executes the agent with the given user message using ReAct architecture:
    1) Load state
    2) Detect if completed todolist should be reset for new query
    3) Reset mission and todolist if needed (multi-turn support)
    4) Set mission (only on first call or after reset)
    5) Answer pending question (if any)
    6) Create plan (if not exists)
    7) Run ReAct loop

    Args:
        user_message: The user message to execute the agent.
        session_id: The session id to execute the agent.

    Returns:
        An async iterator of AgentEvent.
    """
    # 1. State laden (existing)
    self.state = await self.state_manager.load_state(session_id)
    self.logger.info("execute_start", session_id=session_id)

    # 2. Check for completed todolist on new input (Story 1)
    should_reset_mission = False
    previous_todolist_id: Optional[str] = None
    
    if not self.state.get("pending_question"):
        todolist_id = self.state.get("todolist_id")
        
        if todolist_id:
            try:
                existing_todolist = await self.todo_list_manager.load_todolist(todolist_id)
                
                if self._is_plan_complete(existing_todolist):
                    should_reset_mission = True
                    previous_todolist_id = todolist_id
                    self.logger.info(
                        "completed_todolist_detected_on_new_input",
                        session_id=session_id,
                        todolist_id=todolist_id,
                        will_reset=True
                    )
            except FileNotFoundError:
                self.logger.warning(
                    "todolist_file_not_found",
                    session_id=session_id,
                    todolist_id=todolist_id
                )
    
    # 3. NEW: Execute mission reset if needed
    if should_reset_mission:
        self.logger.info(
            "resetting_mission_for_new_query",
            session_id=session_id,
            previous_mission_preview=self.mission[:100] if self.mission else None,
            previous_todolist_id=previous_todolist_id,
            new_query_preview=user_message[:100]
        )
        
        # Clear mission and todolist reference to allow fresh start
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
            # Continue execution despite save failure
        
        # Notify CLI that reset occurred
        yield AgentEvent(
            type=AgentEventType.STATE_UPDATED,
            data={
                "mission_reset": True,
                "reason": "completed_todolist_detected",
                "previous_todolist_id": previous_todolist_id
            }
        )
        
        self.logger.info("mission_reset_complete", session_id=session_id)
    
    # 4. Mission setzen (existing logic, now handles reset case)
    if self.mission is None:
        self.mission = user_message
        self.logger.info("mission_set", session_id=session_id, mission_preview=self.mission[:100])

    # 5. Pending Question beantworten (existing, unchanged)
    if self.state.get("pending_question"):
        # ... existing code unchanged ...
        pass
    
    # 6. Plan erstellen (existing, unchanged)
    todolist_existed = self.state.get("todolist_id") is not None
    todolist = await self._get_or_create_plan(session_id)
    
    # ... rest continues unchanged ...
```

### CLI Display Enhancement (Optional)

**File:** `capstone/agent_v2/cli/commands/rag.py`

**Location:** Lines 189-218 (STATE_UPDATED event handling)

**Optional Enhancement:**
```python
elif event_type == "state_updated":
    # ... existing state update handlers ...
    
    # NEW: Handle mission reset event
    elif event_data.get('mission_reset'):
        if verbose or debug:
            console.print("[dim]🔄 Starting new query (previous task completed)[/dim]")
```

### Testing Strategy

**Unit Tests Location:** `tests/unit/test_agent_execute.py`

**Test Cases:**

1. **Test: Mission Reset Clears State**
   ```python
   async def test_mission_reset_clears_state():
       """Should clear mission and remove todolist_id from state."""
       # Setup: Agent with completed todolist
       # Action: Call execute with new query
       # Assert: mission = None (then set to new query)
       # Assert: todolist_id removed from state
       # Assert: State saved
   ```

2. **Test: Mission Reset Emits Event**
   ```python
   async def test_mission_reset_emits_event():
       """Should emit STATE_UPDATED event with reset info."""
       # Setup: Agent with completed todolist
       # Action: Call execute, collect events
       # Assert: STATE_UPDATED event emitted
       # Assert: Event contains mission_reset=True
       # Assert: Event contains previous_todolist_id
   ```

3. **Test: New Todolist Created After Reset**
   ```python
   async def test_new_todolist_created_after_reset():
       """Should create new todolist with new mission."""
       # Setup: Agent with completed todolist
       # Action: Call execute with new query
       # Assert: New todolist created
       # Assert: New todolist_id in state (different from previous)
       # Assert: New todolist references new mission
   ```

4. **Test: Reset Preserves Other State Fields**
   ```python
   async def test_reset_preserves_other_state():
       """Should preserve answers and other state fields."""
       # Setup: State with answers and completed todolist
       # Action: Reset mission
       # Assert: answers still in state
       # Assert: Only todolist_id removed
   ```

5. **Test: No Reset for Single Mission**
   ```python
   async def test_no_reset_for_single_mission():
       """Should not reset for traditional single-mission usage."""
       # Setup: Agent used once, not yet complete
       # Action: Call execute
       # Assert: No reset triggered
       # Assert: Original mission preserved
   ```

## Dependencies

**Depends On:**
- Story 1: Detect Completed Todolist on New Query (provides detection flag)

**Blocks:**
- Story 3: Integration Testing and CLI Validation (needs reset working)

**Related Code:**
- `StateManager.save_state()` - Persists state changes
- `Agent._get_or_create_plan()` - Creates new todolist
- `AgentEventType.STATE_UPDATED` - Event type
- `AgentEvent` dataclass - Event structure

## Definition of Done

- [x] Reset logic implemented in `Agent.execute()`
- [x] Mission cleared when reset triggered
- [x] Todolist reference removed from state
- [x] State saved after reset
- [x] Event emitted for reset
- [x] All unit tests written and passing
- [x] No regression in existing agent behavior
- [x] Code review completed
- [x] Type annotations complete
- [x] PEP8 compliant
- [x] Logging complete and tested
- [x] Documentation updated

## Testing Checklist

- [ ] Unit test: Mission reset clears state
- [ ] Unit test: Reset emits event
- [ ] Unit test: New todolist created after reset
- [ ] Unit test: Reset preserves other state fields
- [ ] Unit test: No reset for single mission
- [ ] Manual test: RAG CLI multi-turn conversation
- [ ] Manual test: Verify state files after reset
- [ ] Manual test: Check logs for reset events
- [ ] Integration test: Multi-query scenario (Story 3)

## Notes

- Reset is transparent to user (no CLI confirmation needed)
- Session continues (same session_id, same state file)
- New todolist created automatically by existing flow
- Event emission allows CLI to optionally display reset
- Minimal changes to existing code
- Leverages existing mission initialization logic
- State file format unchanged (backward compatible)

