# Story 1: Detect Completed Todolist on New Query

**Epic:** Multi-Turn Conversation Support - Brownfield Enhancement  
**Story ID:** MULTI-TURN-001  
**Status:** Ready for Review  
**Priority:** High  
**Estimated Effort:** 1 day  

## Story Description

Add detection logic in `Agent.execute()` to identify when a new user message arrives with an already-completed todolist. This detection must distinguish between a user answering a pending question (which should continue the existing mission) and a user asking a new independent query (which should trigger a reset).

## User Story

**As a** RAG CLI user  
**I want** the agent to recognize when I'm starting a new query after completing a previous one  
**So that** the agent can prepare to process my new question instead of immediately returning "Task completed"

## Acceptance Criteria

### Functional Requirements

1. **Completion Detection Logic**
   - [x] Add check in `Agent.execute()` after state loading (after line 373)
   - [x] Load existing todolist if `todolist_id` exists in state
   - [x] Use `_is_plan_complete()` method to check if todolist is complete
   - [x] Only trigger for new queries (not when answering pending questions)

2. **Pending Question Differentiation**
   - [x] Check for `pending_question` in state (existing logic at line 381)
   - [x] If pending question exists: DO NOT reset (user is answering)
   - [x] If no pending question AND todolist complete: Flag for reset
   - [x] Preserve existing pending question flow unchanged

3. **Edge Case Handling**
   - [x] Handle case where todolist_id exists but file not found
   - [x] Handle case where no todolist exists yet (first query)
   - [x] Handle case where todolist exists but not complete (in progress)
   - [x] Handle case where mission is None (already reset)

4. **Logging**
   - [x] Log when completed todolist is detected on new input
   - [x] Log distinction between pending question vs new query
   - [x] Use structlog with session_id context
   - [x] Log todolist status (completed/in_progress)

### Technical Requirements

1. **Code Location**
   - Modify: `capstone/agent_v2/agent.py`
   - Method: `Agent.execute()` (starting at line 355)
   - Insert detection logic after line 373 (after state loading)
   - Before line 376 (before mission setting)

2. **Implementation Pattern**
   ```python
   # Pseudo-code structure:
   async def execute(self, user_message: str, session_id: str):
       # 1. Load state (existing)
       self.state = await self.state_manager.load_state(session_id)
       
       # 2. NEW: Check if we have a completed todolist and should reset
       should_reset_mission = False
       
       if not self.state.get("pending_question"):  # Not answering a question
           todolist_id = self.state.get("todolist_id")
           if todolist_id:
               try:
                   existing_todolist = await self.todo_list_manager.load_todolist(todolist_id)
                   if self._is_plan_complete(existing_todolist):
                       should_reset_mission = True
                       self.logger.info("completed_todolist_detected", 
                                      session_id=session_id,
                                      todolist_id=todolist_id)
               except FileNotFoundError:
                   # Todolist file missing, will create new one
                   pass
       
       # 3. Continue with existing mission logic (modified in Story 2)
       # ...
   ```

3. **Type Annotations**
   - [x] All new variables properly typed
   - [x] Use `Optional[str]` for todolist_id
   - [x] Use `bool` for should_reset_mission flag
   - [x] Use `TodoList` type for existing_todolist

4. **Error Handling**
   - [x] Wrap todolist loading in try/except for FileNotFoundError
   - [x] Log errors with context (session_id, todolist_id)
   - [x] Gracefully handle missing todolist files
   - [x] Don't crash if `_is_plan_complete()` fails

### Code Quality Requirements

1. **Python Best Practices**
   - [x] PEP8 compliant formatting
   - [x] Type annotations on all variables
   - [x] Docstring update for `execute()` method (if logic description needed)
   - [x] Clear variable names (e.g., `should_reset_mission`, not `reset`)
   - [x] Comments explaining the "why" of the check

2. **Logging Best Practices**
   - [x] Use structlog with logger.info/warning/error
   - [x] Include context: session_id, todolist_id, mission status
   - [x] No sensitive data in logs
   - [x] Structured log fields (no free-form strings)

3. **Testing**
   - [x] Unit test: Detect completion when todolist complete
   - [x] Unit test: Skip detection when pending question exists
   - [x] Unit test: Handle missing todolist file gracefully
   - [x] Unit test: Handle no todolist_id in state

### Backward Compatibility

1. **Existing Flows Must Work**
   - [x] Single-mission agents: Detection doesn't break existing behavior
   - [x] Pending questions: No interference with question/answer flow
   - [x] First query: No issue when no todolist exists yet
   - [x] In-progress missions: Don't reset when todolist incomplete

2. **No API Changes**
   - [x] `execute()` signature unchanged
   - [x] No new required parameters
   - [x] Return type unchanged (AsyncIterator[AgentEvent])
   - [x] Event types unchanged

3. **State Compatibility**
   - [x] No new state fields required in this story
   - [x] Existing state structure preserved
   - [x] Todolist files remain unchanged

## Implementation Details

### File Changes

**File:** `capstone/agent_v2/agent.py`

**Location:** Lines 355-404 (Agent.execute method)

**Changes:**
1. After line 373 (state loading), add completion detection block
2. Store result in `should_reset_mission` boolean flag
3. Use flag in Story 2 for actual reset logic

### Code Structure

```python
async def execute(self, user_message: str, session_id: str) -> AsyncIterator[AgentEvent]:
    """
    Executes the agent with the given user message using ReAct architecture:
    1) Load state
    2) Detect if completed todolist should be reset for new query
    3) Set mission (only on first call or after reset)
    4) Answer pending question (if any)
    5) Create plan (if not exists)
    6) Run ReAct loop

    Args:
        user_message: The user message to execute the agent.
        session_id: The session id to execute the agent.

    Returns:
        An async iterator of AgentEvent.
    """
    # 1. State laden (existing)
    self.state = await self.state_manager.load_state(session_id)
    self.logger.info("execute_start", session_id=session_id)

    # 2. NEW: Check for completed todolist on new input
    should_reset_mission = False
    
    # Only check if NOT answering a pending question
    if not self.state.get("pending_question"):
        todolist_id = self.state.get("todolist_id")
        
        if todolist_id:
            try:
                # Load existing todolist to check completion status
                existing_todolist = await self.todo_list_manager.load_todolist(todolist_id)
                
                # Check if all tasks are completed
                if self._is_plan_complete(existing_todolist):
                    should_reset_mission = True
                    self.logger.info(
                        "completed_todolist_detected_on_new_input",
                        session_id=session_id,
                        todolist_id=todolist_id,
                        will_reset=True
                    )
            except FileNotFoundError:
                # Todolist file doesn't exist, will create new one anyway
                self.logger.warning(
                    "todolist_file_not_found",
                    session_id=session_id,
                    todolist_id=todolist_id
                )
    
    # 3. Mission reset logic (Story 2 will implement)
    # if should_reset_mission:
    #     # Reset mission and clear todolist_id
    #     pass
    
    # 4. Mission setzen (existing logic continues)
    # ... rest of method unchanged ...
```

### Testing Strategy

**Unit Tests Location:** `tests/unit/test_agent_execute.py` (new or extend existing)

**Test Cases:**

1. **Test: Detect Completed Todolist**
   ```python
   async def test_detect_completed_todolist_on_new_input():
       """Should detect when todolist is complete and flag for reset."""
       # Setup: Agent with completed todolist in state
       # Action: Call execute with new user message
       # Assert: should_reset_mission = True
       # Assert: Appropriate log message emitted
   ```

2. **Test: Skip Detection for Pending Questions**
   ```python
   async def test_skip_detection_when_answering_question():
       """Should NOT reset when user is answering pending question."""
       # Setup: Agent with pending_question in state
       # Action: Call execute with answer
       # Assert: should_reset_mission = False (not set)
       # Assert: Existing question flow continues
   ```

3. **Test: Handle Missing Todolist File**
   ```python
   async def test_handle_missing_todolist_file():
       """Should handle gracefully when todolist file is missing."""
       # Setup: State has todolist_id but file doesn't exist
       # Action: Call execute
       # Assert: No crash, warning logged
       # Assert: Execution continues normally
   ```

4. **Test: No Detection on First Query**
   ```python
   async def test_no_detection_when_no_todolist():
       """Should not attempt detection when no todolist exists."""
       # Setup: Fresh state with no todolist_id
       # Action: Call execute with first query
       # Assert: No detection logic triggered
       # Assert: Normal first-query flow
   ```

5. **Test: Skip Detection for Incomplete Todolist**
   ```python
   async def test_skip_detection_when_todolist_incomplete():
       """Should NOT reset when todolist is still in progress."""
       # Setup: Agent with in-progress todolist
       # Action: Call execute with follow-up input
       # Assert: should_reset_mission = False
       # Assert: Continue existing mission
   ```

## Dependencies

**Depends On:**
- None (first story in epic)

**Blocks:**
- Story 2: Reset Mission and Create Fresh Todolist (needs the detection flag)

**Related Code:**
- `Agent._is_plan_complete()` - Used to check todolist status
- `TodoListManager.load_todolist()` - Loads existing todolist
- `StateManager.load_state()` - Loads session state
- Existing pending question logic (lines 381-388)

## Definition of Done

- [x] Detection logic implemented in `Agent.execute()`
- [x] Distinguishes pending questions from new queries
- [x] All edge cases handled (missing file, no todolist, incomplete)
- [x] Logging added with appropriate context
- [x] All unit tests written and passing
- [x] No regression in existing agent behavior
- [x] Code review completed
- [x] Type annotations complete
- [x] PEP8 compliant
- [x] Documentation updated (docstring if needed)

## Testing Checklist

- [x] Unit test: Detect completed todolist
- [x] Unit test: Skip detection for pending questions
- [x] Unit test: Handle missing todolist file
- [x] Unit test: No detection on first query
- [x] Unit test: Skip detection for incomplete todolist
- [ ] Manual test: Run RAG CLI and complete first query
- [ ] Manual test: Verify log messages appear correctly
- [ ] Integration test: Multi-query scenario (in Story 3)

## Dev Agent Record

### File List
**Modified Files:**
- `capstone/agent_v2/agent.py` - Added detection logic in `execute()` method (lines 376-404)

**New Files:**
- `capstone/agent_v2/tests/test_agent_execute.py` - Created comprehensive unit tests for detection logic

### Completion Notes
- All 5 unit tests passing successfully
- Detection logic implemented with proper type annotations
- Edge cases handled: missing files, pending questions, incomplete todolists
- Logging implemented with structured context
- No linter errors
- Backward compatibility maintained

### Change Log
- Added completion detection logic after state loading in `Agent.execute()`
- Detection only runs when no pending question exists
- Flag `should_reset_mission` set for Story 2 to use
- Created 5 comprehensive unit tests covering all scenarios
- Updated docstring to reflect new step in execution flow

## Notes

- This story only adds DETECTION, not the actual reset
- Detection result stored in local variable for Story 2 to use
- No state changes in this story
- Focus on correctness and edge case handling
- Logging is critical for debugging and observability
- Must not break any existing functionality

## QA Results

### Review Date: 2025-01-12

### Reviewed By: Quinn (Test Architect)

### Code Quality Assessment

**Overall Grade: Excellent (A-)**

This implementation demonstrates high-quality software engineering practices with comprehensive test coverage, proper error handling, and excellent maintainability. The detection logic is clean, well-documented, and correctly implements all acceptance criteria. The code follows Python best practices with full type annotations, structured logging, and clear separation of concerns.

**Key Strengths:**
- ✅ All 5 unit tests passing with comprehensive edge case coverage
- ✅ Proper type annotations throughout (`bool`, `Optional[str]`, `TodoList`)
- ✅ Structured logging with session context for production observability
- ✅ Graceful error handling (FileNotFoundError properly caught and logged)
- ✅ Backward compatible (no API changes, existing flows preserved)
- ✅ Clear inline comments explaining the "why" not just the "what"
- ✅ PEP8 compliant, no linter errors

**Minor Observations:**
- `should_reset_mission` flag is set but not used (expected - waiting for Story 2)
- Todolist loaded twice in execution flow: once for detection (line 387), once in `_get_or_create_plan` (line 422) - minor performance inefficiency but not critical at current scale

### Refactoring Performed

**No refactoring performed during review.** The code quality is excellent as-is. The minor performance optimization opportunity (double-load pattern) is noted for future consideration but does not warrant immediate refactoring.

### Compliance Check

- **Coding Standards**: ✓ PASS
  - Full type annotations present
  - Structured logging with context
  - Clear variable names
  - PEP8 compliant
  
- **Project Structure**: ✓ PASS
  - Implementation in correct location (`capstone/agent_v2/agent.py`)
  - Tests properly organized (`capstone/agent_v2/tests/test_agent_execute.py`)
  - Follows established patterns
  
- **Testing Strategy**: ✓ PASS
  - Comprehensive unit test coverage (5 tests)
  - Proper use of mocking for isolation
  - Edge cases thoroughly covered
  - Integration tests deferred to Story 3 (appropriate)
  
- **All ACs Met**: ✓ PASS
  - All 4 functional requirement groups fully implemented
  - All technical requirements satisfied
  - All code quality requirements met
  - Edge cases properly handled

### Requirements Traceability (Given-When-Then)

| AC # | Test Case | Coverage |
|------|-----------|----------|
| AC-1: Completion Detection | `test_detect_completed_todolist_on_new_input` | ✓ COVERED |
| **Given**: State with completed todolist, no pending question |
| **When**: User sends new message |
| **Then**: should_reset_mission=True, detection log emitted |
| | |
| AC-2: Pending Question Differentiation | `test_skip_detection_when_answering_question` | ✓ COVERED |
| **Given**: State with pending question AND completed todolist |
| **When**: User sends answer to pending question |
| **Then**: Detection does NOT run, pending question flow continues |
| | |
| AC-3a: Edge Case - Missing File | `test_handle_missing_todolist_file` | ✓ COVERED |
| **Given**: State has todolist_id but file doesn't exist |
| **When**: Execute called with new message |
| **Then**: Warning logged, no crash, execution continues gracefully |
| | |
| AC-3b: Edge Case - No Todolist | `test_no_detection_when_no_todolist` | ✓ COVERED |
| **Given**: Fresh state with no todolist_id (first query) |
| **When**: User sends first query |
| **Then**: Detection not attempted, load_todolist not called |
| | |
| AC-3c: Edge Case - Incomplete Todolist | `test_skip_detection_when_todolist_incomplete` | ✓ COVERED |
| **Given**: State with in-progress todolist |
| **When**: User sends follow-up message |
| **Then**: Detection does NOT flag for reset, continues existing mission |
| | |
| AC-4: Logging Requirements | All tests verify logging | ✓ COVERED |
| **Given**: Various detection scenarios |
| **When**: Detection runs or is skipped |
| **Then**: Appropriate structured logs emitted with session context |

**Coverage Summary**: 6/6 acceptance criteria fully covered with unit tests (100%)

### Test Architecture Quality

**Unit Test Assessment: Excellent**

The test suite demonstrates professional-quality test architecture:

- **Isolation**: Proper use of `AsyncMock` and `MagicMock` for complete test isolation
- **Fixtures**: Well-organized pytest fixtures for reusable test components
- **Clarity**: Test names clearly describe scenarios (implicit Given-When-Then)
- **Assertions**: Both behavior and logging verified (supports observability)
- **Edge Cases**: Comprehensive coverage of error conditions and boundary cases
- **Maintainability**: Clean test code that's easy to understand and extend

**Test Level Appropriateness**: ✓ Correct

Unit tests are the appropriate level for this detection logic. Integration tests appropriately deferred to Story 3 (Multi-Query Scenario).

### Security Review

**Status**: ✓ PASS - No Concerns

- No user input handling changes
- No authentication/authorization changes  
- No data persistence changes (flag stored in local variable only)
- Detection logic is internal state management only
- Logging does not expose sensitive data (only session_id and todolist_id)

### Performance Considerations

**Status**: ⚠ MINOR CONCERN (Not Blocking)

**Finding**: Todolist loaded twice during execute flow
- Line 387: Loaded for detection check
- Line 422-423: Loaded again in `_get_or_create_plan()`

**Impact**: Low - Extra file I/O operation per new query after completion
**Probability**: High (occurs on every new query after completion)  
**Risk Score**: 3/10 (Low priority)

**Recommendation**: Consider caching the loaded todolist from detection to reuse in `_get_or_create_plan()`. This is a minor optimization that can be addressed in future refactoring - not critical for current scale.

### Files Modified During Review

**None** - No files modified during QA review. Code quality is excellent as-is.

### Gate Status

**Gate**: ✅ **PASS**

Gate details: `docs/qa/gates/multi-turn-001-detect-completed-todolist.yml`

**Quality Score**: 90/100
- Base: 100
- Minor performance concern: -10
- No other deductions

**NFR Summary**:
- Security: PASS
- Performance: CONCERNS (minor, non-blocking)
- Reliability: PASS  
- Maintainability: PASS

### Recommended Next Steps

1. ✅ **Story Status**: Ready to move to **Done**
2. ⏭️ **Next Story**: Proceed to Story 2 (Reset Mission and Create Fresh Todolist)
3. 📋 **Future Optimization**: Consider double-load optimization in future performance sprint
4. 🧪 **Integration Testing**: Will be validated in Story 3

### Recommended Status

**✓ Ready for Done**

All acceptance criteria met, comprehensive test coverage, no blocking issues. The minor performance observation is noted for future optimization but does not block completion.

(Story owner decides final status)

---

**Test Architect Notes**: Excellent implementation quality. The team demonstrated strong engineering practices with comprehensive testing, proper error handling, and clear documentation. The unused `should_reset_mission` flag and double-load pattern are expected/acceptable at this stage of the epic. Looking forward to Story 2 completing the reset functionality!

