# Epic: Conversation History Preservation - Brownfield Enhancement

## Epic Goal

Enable the RAG agent to preserve conversation history across multiple queries while maintaining task-specific TodoList resets, allowing the LLM to reference previous conversation context for follow-up questions and maintaining natural conversational flow.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- Multi-turn conversation support implemented (Epic: multi-turn-conversation-epic.md)
- Mission and TodoList reset on query completion (lines 377-444 in `agent.py`)
- MessageHistory class manages conversation history (lines 73-183 in `agent.py`)
- MessageHistory is initialized once in `Agent.__init__()` (line 348) and never reset
- **Bug:** MessageHistory persists across mission resets, causing LLM to see old context and return cached answers
- Current behavior: Second query receives same answer as first query due to persistent message history

**Technology stack:**
- Python 3.11+ with async/await patterns
- ReAct agent architecture (Thought → Action → Observation loop)
- MessageHistory class with automatic compression (MAX_MESSAGES=50, SUMMARY_THRESHOLD=40)
- LLM conversation context management
- structlog for logging
- State persistence via `StateManager`

**Integration points:**
- `Agent.execute()` method - Mission reset logic (lines 377-444)
- `MessageHistory` class - Conversation history management (lines 73-183)
- `_generate_thought_with_context()` - LLM thought generation (line 717-745)
- `build_system_prompt()` function - System prompt construction
- `_react_loop()` - Main execution loop with message history usage

### Enhancement Details

**What's being added/changed:**

1. **Conversation-Aware History Management:**
   - **Do NOT reset** MessageHistory on mission reset (unlike current buggy behavior)
   - Preserve conversation context across multiple queries for follow-up questions
   - Allow LLM to reference previous answers: "What you just explained about..."
   - Maintain natural conversational flow: Query 1 → Answer 1 → Query 2 (references Q1) → Answer 2

2. **System Prompt Redesign:**
   - Separate mission from system prompt to allow stable system context
   - Store system prompt template in `Agent` for rebuilding
   - Make system prompt mission-agnostic (tools, role, behavior only)
   - Treat each user query as a natural conversation message, not embedded in system prompt

3. **History Compression for Long Conversations:**
   - Leverage existing `MessageHistory.compress_history_async()` (lines 102-140)
   - Automatically compress when exceeding SUMMARY_THRESHOLD (40 messages)
   - Preserve key context while managing token limits
   - Log compression events for observability

**How it integrates:**
- Modify mission reset block in `Agent.execute()` to **skip** MessageHistory reset
- Update `Agent.__init__()` to store system prompt template separately
- Update `build_system_prompt()` to create mission-agnostic prompts
- Add optional history compression trigger during mission reset for long conversations
- Maintain all existing mission/TodoList reset behavior
- Backward compatible: Single-mission agents see no behavior change

**Success criteria:**
- User can ask follow-up questions that reference previous answers
- Second query receives contextually appropriate answer, not cached first answer
- LLM can say "As I mentioned earlier..." when relevant
- Conversation history preserved across TodoList resets
- Automatic compression prevents token overflow in long conversations
- Each query still gets fresh TodoList (existing behavior preserved)
- No regression in single-mission agent workflows
- Proper logging of history management events

## Stories

### Story 1: Remove MessageHistory Reset from Mission Reset
**Priority:** Critical  
**Estimated Effort:** 0.5 days

Fix the bug where MessageHistory is incorrectly reset on mission completion, causing the LLM to see stale context and return cached answers instead of processing new queries.

**Key Tasks:**
- Remove any MessageHistory reset/reinitialization in mission reset block (lines 409-444)
- Add logging to confirm history preservation across mission resets
- Add message count to mission reset event for observability
- Verify that conversation context flows across queries
- Test that second query gets fresh processing with historical context

**Acceptance Criteria:**
- MessageHistory is NOT reset when mission is reset
- Second query receives different answer than first query
- LLM can see both previous query and answer in context
- Logging shows message count preserved across resets

### Story 2: System Prompt Decoupling from Mission
**Priority:** High  
**Estimated Effort:** 1 day

Decouple mission from system prompt to maintain stable LLM context across multiple queries, treating each user query as a natural conversation message.

**Key Tasks:**
- Store system prompt template in `Agent.__init__()` (without mission embedded)
- Update `build_system_prompt()` to create mission-agnostic prompts
- Remove mission from system prompt structure
- Treat user queries as normal user messages in conversation flow
- Update MessageHistory initialization to use mission-agnostic system prompt
- Add tests for system prompt stability across missions

**Acceptance Criteria:**
- System prompt does not contain mission-specific text
- System prompt remains stable across multiple queries
- User queries appear as natural conversation messages
- build_system_prompt() accepts None for mission parameter
- No regression in ReAct loop behavior

### Story 3: Automatic History Compression Management
**Priority:** Medium  
**Estimated Effort:** 0.5 days

Add intelligent history compression during mission reset for long conversations to prevent token overflow while preserving essential context.

**Key Tasks:**
- Add compression check during mission reset
- Trigger `compress_history_async()` when message count exceeds threshold
- Add configuration option for compression trigger point
- Log compression events with before/after message counts
- Test compression with multi-query conversation scenarios

**Acceptance Criteria:**
- Compression triggered automatically when threshold exceeded
- Conversation context preserved in summary
- Token limits respected in long conversations
- Logging shows compression events clearly
- Compression does not break conversation flow

## Compatibility Requirements

- [x] Existing APIs remain unchanged (`execute()` signature preserved)
- [x] Single-mission agent behavior unchanged (no breaking changes)
- [x] TodoList reset behavior preserved (from multi-turn epic)
- [x] Pending question logic unaffected
- [x] State persistence format unchanged
- [x] MessageHistory class interface unchanged
- [x] Performance impact minimal (no new API calls)
- [x] Backward compatible with existing mission-based agents

## Risk Mitigation

**Primary Risk:** MessageHistory growing unbounded in very long conversation sessions

**Mitigation:**
- Leverage existing automatic compression (SUMMARY_THRESHOLD=40 messages)
- Add explicit compression trigger during mission reset
- MessageHistory already has MAX_MESSAGES=50 safety limit
- Implement logging for history size monitoring
- Existing compression logic proven in production

**Secondary Risk:** Breaking existing agent behavior expecting fresh context

**Mitigation:**
- Single-mission agents unaffected (only execute once, no reset)
- Feature only affects multi-turn RAG CLI sessions
- Extensive testing of both conversation and isolated modes
- Rollback plan is simple (revert Story 1 changes)

**Rollback Plan:**
- Story 1: Revert removal of MessageHistory reset (single file, single location)
- Story 2: Revert system prompt changes (single file, single function)
- Story 3: Compression is optional enhancement, can be disabled
- No state file changes (rollback compatible)
- No external dependencies added
- Can rollback via git revert of specific commits

## Definition of Done

- [x] All stories completed with acceptance criteria met
- [x] RAG CLI supports conversational follow-up questions
- [x] Second query receives contextually appropriate answer (bug fixed)
- [x] LLM can reference previous conversation in responses
- [x] Automatic history compression prevents token overflow
- [x] TodoList reset behavior preserved (each query gets fresh plan)
- [x] Existing single-mission agent functionality verified (no regressions)
- [x] Integration tests pass for conversational scenarios
- [x] Code follows Python best practices:
  - PEP8 compliant
  - Full type annotations
  - Docstrings (Google/NumPy style)
  - Proper error handling
  - Structured logging with context
- [x] Documentation updated with conversation flow explanation
- [x] No linter errors introduced

## Technical Constraints

- **Do NOT change:**
  - `Agent.execute()` signature
  - `MessageHistory` class interface
  - State file format/schema
  - TodoList structure
  - Tool interfaces
  - CLI command signatures

- **Must preserve:**
  - TodoList reset on mission completion (from multi-turn epic)
  - Pending question flow
  - Single-mission agent behavior
  - State persistence patterns
  - ReAct loop integrity
  - Async/await patterns
  - Existing compression algorithm

- **Follow existing patterns:**
  - Use structlog with bind context
  - Maintain async/await throughout
  - Type annotations on all functions
  - Docstrings with Args/Returns/Raises
  - Error handling with try/except and logging

## Files to Modify

**Primary Changes:**
- `capstone/agent_v2/agent.py`:
  - `Agent.__init__()` - Store system prompt template
  - `Agent.execute()` - Remove MessageHistory reset, add compression trigger
  - `MessageHistory` class - No interface changes, only usage changes
  - `build_system_prompt()` function - Support mission-agnostic prompts

**Testing:**
- `tests/integration/test_conversation_history_preservation.py` (new)
- Update `tests/integration/test_multi_turn_conversation.py` to verify history preservation
- Add test cases for system prompt stability

**Documentation:**
- Update `Agent.execute()` docstring to explain history preservation
- Add comments explaining conversation vs task context separation
- Document compression behavior in MessageHistory class

## Success Metrics

**Before Fix:**
- ❌ Second query returns same answer as first query (cached response bug)
- ❌ LLM sees stale message history and continues from wrong step
- ❌ Cannot ask follow-up questions like "What you just explained..."
- ❌ No conversational continuity across queries

**After Fix:**
- ✅ Each query receives contextually appropriate answer
- ✅ LLM can reference previous conversation naturally
- ✅ Follow-up questions work: "Tell me more about..." references previous answer
- ✅ Conversational flow maintained across multiple queries
- ✅ TodoList still resets per query (task isolation preserved)
- ✅ Automatic compression prevents token overflow

## Related Issues

- **Fixes:** Current bug where second query returns first query's answer
- **Builds on:** Multi-turn conversation epic (mission/TodoList reset)
- **Enables:** True conversational RAG interactions
- **Improves:** User experience with natural follow-up questions
- **Maintains:** Task isolation (each query gets fresh TodoList)

## Dependencies

**Internal:**
- `Agent` class (agent.py) - Mission reset logic
- `MessageHistory` class (agent.py) - History management
- `build_system_prompt()` function (prompts module)
- `StateManager` (statemanager.py) - No changes needed
- `TodoListManager` (planning/todolist.py) - No changes needed

**External:**
- No new external dependencies required
- Uses existing Python stdlib and installed packages
- Leverages existing LLM completion API

## Timeline

**Total Estimated Time:** 2 days

- Story 1 (Remove Reset Bug): 0.5 days
- Story 2 (System Prompt Decoupling): 1 day
- Story 3 (Compression Management): 0.5 days

**Sequencing:**
- Story 1 is critical and should be completed first (bug fix)
- Story 2 can be done in parallel or after Story 1
- Story 3 is optional enhancement, can be done last

## Notes

- This is a targeted enhancement that fixes a critical bug AND adds conversational capability
- Story 1 alone fixes the immediate bug (second query getting first answer)
- Stories 2-3 improve the architecture for better long-term conversation management
- Changes are focused and localized to conversation management
- High impact on user experience with conversational interactions
- Low risk due to isolated scope and existing compression infrastructure
- Easy to test with multi-query conversation scenarios
- Easy to rollback if issues arise (minimal surface area)

## Example Use Case

**Before (Current Bug):**
```
User: "Wie funktioniert der Plankalender?"
Agent: [Detailed explanation about Plankalender]

User: "Gibt es verschiedene Arbeitszeitmodelle?"
Agent: [Same Plankalender explanation - WRONG!]
```

**After (With This Epic):**
```
User: "Wie funktioniert der Plankalender?"
Agent: [Detailed explanation about Plankalender]

User: "Gibt es verschiedene Arbeitszeitmodelle?"
Agent: [New search and explanation about Arbeitszeitmodelle]

User: "Wie hängen diese Modelle mit dem Plankalender zusammen, den du gerade erklärt hast?"
Agent: [Contextual answer referencing both previous topics]
```

This demonstrates:
1. Each query gets fresh processing (TodoList reset)
2. Conversation history allows contextual follow-up
3. LLM can reference previous answers naturally

