# Epic: Multi-Turn Conversation Support - Brownfield Enhancement

## Epic Goal

Enable the RAG agent CLI to handle multiple consecutive user queries in a single session, where each query is treated as an independent task with its own todolist, allowing natural multi-turn conversations without the "soft completion" bug.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- RAG agent (`create_rag_agent`) executes one mission per session
- Mission is set once in `Agent.execute()` (line 376-378 in `agent.py`)
- After todolist completion, subsequent queries immediately complete without processing
- User must restart CLI session to ask new questions
- "Soft completion" bug: Agent returns "✅ Task completed!" for every new query after first completion

**Technology stack:**
- Python 3.11+ with async/await patterns
- ReAct agent architecture (Thought → Action → Observation loop)
- Typer CLI with Rich console output
- structlog for logging
- State persistence via `StateManager`
- Task planning via `TodoListManager`

**Integration points:**
- `Agent.execute()` method - Main execution entry point
- `_get_or_create_plan()` - Todolist creation and loading
- `_is_plan_complete()` - Completion check
- `_react_loop()` - Main execution loop
- CLI chat loop in `rag.py` - User input handling
- `StateManager` - Session state persistence
- `TodoListManager` - Task planning and management

### Enhancement Details

**What's being added/changed:**

1. **Completion Detection on New Input:**
   - Add logic in `Agent.execute()` to detect when a new user message arrives with an already-completed todolist
   - Differentiate between "answering pending question" (keep mission) vs "new independent query" (reset mission)
   - Check if current todolist exists and all tasks are completed/skipped

2. **Mission Reset for New Queries:**
   - When completed todolist detected on new user input (not answering question):
     - Clear current mission (`self.mission = None`)
     - Remove todolist reference from state (`self.state.pop("todolist_id")`)
     - Emit state update event
     - Let normal execution flow create new todolist for new query
   - Preserve session state structure (same session_id, same state file)

3. **Preserve Pending Question Flow:**
   - No changes to pending question logic (lines 381-388 in `agent.py`)
   - If user is answering an agent question, keep existing mission and todolist
   - Only reset for truly new independent queries

**How it integrates:**
- Modify `Agent.execute()` to add completion check before mission initialization
- Use existing `_is_plan_complete()` method to check todolist status
- Leverage existing `StateManager` save/load for persistence
- No changes to CLI loop (works transparently with fixed agent)
- Backward compatible: Single-mission agents unaffected

**Success criteria:**
- User can ask multiple consecutive questions in RAG CLI session
- Each query gets proper agent processing (thought → action → result)
- No more "soft completion" bug after first query completes
- Pending questions still work correctly (user answering agent)
- Existing single-mission agent workflows unaffected
- State files remain compatible
- Proper logging of mission reset events

## Stories

### Story 1: Detect Completed Todolist on New Query
**Priority:** High  
**Estimated Effort:** 1 day

Add detection logic in `Agent.execute()` to identify when a new user message arrives with an already-completed todolist, distinguishing between pending question answers and new independent queries.

**Key Tasks:**
- Add completion check before mission initialization
- Use `_is_plan_complete()` to check todolist status
- Differentiate pending question vs new query
- Add logging for detection events

### Story 2: Reset Mission and Create Fresh Todolist
**Priority:** High  
**Estimated Effort:** 1 day

Implement mission reset logic that clears the completed mission and allows creation of a fresh todolist for the new query, while preserving session state.

**Key Tasks:**
- Clear mission when completed todolist detected
- Remove todolist_id from state
- Emit state update event
- Verify new todolist creation works
- Add logging for mission reset

### Story 3: Integration Testing and CLI Validation
**Priority:** High  
**Estimated Effort:** 1 day

Comprehensive testing of multi-turn conversation scenarios, pending question flows, and backward compatibility with single-mission agents.

**Key Tasks:**
- Create integration test for multi-query scenario
- Test pending question flow preservation
- Validate RAG CLI behavior with multiple queries
- Test single-mission agent backward compatibility
- Add test coverage for edge cases

## Compatibility Requirements

- [x] Existing APIs remain unchanged (`execute()` signature preserved)
- [x] Single-mission agent behavior unchanged (no breaking changes)
- [x] Pending question logic unaffected (lines 381-388)
- [x] State persistence format unchanged (no schema changes)
- [x] UI changes follow existing patterns (Rich console output)
- [x] Performance impact minimal (one additional check per execute)

## Risk Mitigation

**Primary Risk:** Breaking existing agent workflows that expect one mission per session

**Mitigation:**
- Use explicit condition: only reset if (todolist complete AND not answering pending question AND user input provided)
- Comprehensive testing of both multi-turn and single-mission scenarios
- No changes to state file schema (rollback compatible)
- Feature isolated to `Agent.execute()` method
- Logging added for observability

**Rollback Plan:**
- Revert changes to `Agent.execute()` method (single file change)
- State files remain compatible (no schema changes)
- No database or external system changes
- No CLI signature changes
- Can rollback via git revert of specific commits

## Definition of Done

- [x] All stories completed with acceptance criteria met
- [x] RAG CLI supports multiple consecutive queries without "soft completion"
- [x] User can ask follow-up questions without restarting session
- [x] Pending question flow works correctly
- [x] Integration tests pass for both multi-turn and single-mission scenarios
- [x] Existing agent functionality verified (no regressions)
- [x] Code follows Python best practices:
  - PEP8 compliant
  - Full type annotations
  - Docstrings (Google/NumPy style)
  - Proper error handling
  - Structured logging with context
- [x] Documentation updated (if needed)
- [x] No linter errors introduced

## Technical Constraints

- **Do NOT change:**
  - `Agent.execute()` signature
  - State file format/schema
  - TodoList structure
  - Tool interfaces
  - CLI command signatures

- **Must preserve:**
  - Pending question flow
  - Single-mission agent behavior
  - State persistence patterns
  - ReAct loop integrity
  - Async/await patterns

- **Follow existing patterns:**
  - Use structlog with bind context
  - Maintain async/await throughout
  - Type annotations on all functions
  - Docstrings with Args/Returns/Raises
  - Error handling with try/except and logging

## Files to Modify

**Primary Changes:**
- `capstone/agent_v2/agent.py` - `Agent.execute()` method

**Testing:**
- `tests/integration/test_multi_turn_conversation.py` (new)
- Update existing agent tests if needed

**Documentation:**
- Update inline docstrings
- Add comments explaining reset logic

## Success Metrics

**Before Fix:**
- ❌ Second query returns "✅ Task completed!" immediately
- ❌ No thought/action/result cycle for subsequent queries
- ❌ User must restart CLI to ask new questions

**After Fix:**
- ✅ Each query gets full agent processing
- ✅ Multiple queries work in single session
- ✅ Natural conversation flow restored
- ✅ Zero impact on existing agent workflows

## Related Issues

- Fixes the "soft completion" bug reported in RAG CLI
- Enables conversational AI pattern for RAG agent
- Improves user experience (no session restarts needed)
- Maintains backward compatibility with mission-based agents

## Dependencies

**Internal:**
- `Agent` class (agent.py)
- `StateManager` (statemanager.py)
- `TodoListManager` (planning/todolist.py)
- `AgentEventType` enum (agent.py)

**External:**
- No new external dependencies required
- Uses existing Python stdlib and installed packages

## Timeline

**Total Estimated Time:** 3 days

- Story 1 (Detection): 1 day
- Story 2 (Reset): 1 day  
- Story 3 (Testing): 1 day

**Sequencing:**
- Stories must be completed in order (1 → 2 → 3)
- Story 2 depends on Story 1
- Story 3 validates Stories 1 & 2

## Notes

- This is a surgical fix targeting a specific bug
- Changes are minimal and localized to one method
- High impact on user experience
- Low risk due to explicit condition checking
- Easy to test and validate
- Easy to rollback if issues arise

