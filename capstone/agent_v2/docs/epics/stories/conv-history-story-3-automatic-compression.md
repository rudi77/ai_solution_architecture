# Story 3: Automatic History Compression Management

**Epic:** Conversation History Preservation - Brownfield Enhancement  
**Story ID:** CONV-HIST-003  
**Status:** Draft  
**Priority:** Medium  
**Estimated Effort:** 0.5 days  

## Story Description

Add intelligent history compression during mission reset for long conversations to prevent token overflow while preserving essential context. This optimization leverages the existing `MessageHistory.compress_history_async()` functionality to automatically summarize old conversation context when the message count exceeds a threshold.

## User Story

**As a** RAG CLI user  
**I want** the system to automatically manage long conversation history  
**So that** I can have extended multi-query sessions without hitting token limits or performance degradation

## Acceptance Criteria

### Functional Requirements

1. **Compression Trigger During Mission Reset**
   - [ ] Add compression check in mission reset block (after line 421 in agent.py)
   - [ ] Trigger compression when message count > SUMMARY_THRESHOLD (40)
   - [ ] Use existing `MessageHistory.compress_history_async()` method
   - [ ] Compression happens before TodoList reset completes

2. **Leverage Existing Compression Infrastructure**
   - [ ] Use existing `SUMMARY_THRESHOLD = 40` constant from MessageHistory
   - [ ] Use existing `compress_history_async()` method (lines 102-140)
   - [ ] No changes to compression algorithm
   - [ ] No changes to MessageHistory class interface

3. **Compression Event Logging**
   - [ ] Log when compression is triggered
   - [ ] Log message counts before and after compression
   - [ ] Log compression success/failure
   - [ ] Use structured logging with context

4. **Graceful Compression Failure Handling**
   - [ ] If compression fails: Log error and continue
   - [ ] Don't block mission reset on compression failure
   - [ ] Existing fallback: Keep recent messages (from MessageHistory)
   - [ ] System continues to function even if compression unavailable

### Technical Requirements

1. **Code Location**
   - Modify: `capstone/agent_v2/agent.py`
   - Method: `Agent.execute()` mission reset block (around line 421)
   - After: Mission and todolist_id cleared
   - Before: State save
   - Use: Existing `MessageHistory.compress_history_async()` method

2. **Implementation Pattern**
   ```python
   # In mission reset block, after clearing mission/todolist_id:
   if should_reset_mission:
       self.logger.info(
           "resetting_mission_preserving_conversation",
           session_id=session_id,
           # ... existing logging ...
           message_count=len(self.message_history.messages)
       )
       
       # Clear mission and todolist
       self.mission = None
       self.state.pop("todolist_id", None)
       
       # NEW: Trigger compression if history is long
       message_count = len(self.message_history.messages)
       if message_count > self.message_history.SUMMARY_THRESHOLD:
           self.logger.info(
               "triggering_history_compression",
               session_id=session_id,
               message_count_before=message_count,
               threshold=self.message_history.SUMMARY_THRESHOLD
           )
           
           try:
               await self.message_history.compress_history_async()
               
               new_message_count = len(self.message_history.messages)
               self.logger.info(
                   "history_compression_complete",
                   session_id=session_id,
                   message_count_before=message_count,
                   message_count_after=new_message_count,
                   messages_reduced=message_count - new_message_count
               )
           except Exception as e:
               self.logger.error(
                   "history_compression_failed",
                   session_id=session_id,
                   error=str(e),
                   message_count=message_count
               )
               # Continue execution despite compression failure
       
       # Persist state changes (existing)
       await self.state_manager.save_state(session_id, self.state)
       
       # ... rest of reset logic ...
   ```

3. **Type Annotations**
   - [ ] `message_count: int` for tracking
   - [ ] Proper exception typing in error handling
   - [ ] Maintain existing type annotations

4. **Error Handling**
   - [ ] Wrap compression in try/except
   - [ ] Log compression failures with context
   - [ ] Don't re-raise exceptions (non-blocking)
   - [ ] System continues if compression fails

### Code Quality Requirements

1. **Python Best Practices**
   - [ ] PEP8 compliant formatting
   - [ ] Clear variable names (message_count_before, message_count_after)
   - [ ] Comments explaining compression trigger logic
   - [ ] Use existing constants (SUMMARY_THRESHOLD)

2. **Logging Best Practices**
   - [ ] Structured logging with metrics (counts, deltas)
   - [ ] Three log events: trigger, success, failure
   - [ ] Include session_id context
   - [ ] Use appropriate log levels (info for normal, error for failures)

3. **Testing**
   - [ ] Integration test: Long conversation triggers compression
   - [ ] Integration test: Compression reduces message count
   - [ ] Integration test: Context preserved after compression
   - [ ] Integration test: Agent continues after compression
   - [ ] Integration test: Graceful handling of compression failure
   - [ ] Unit test: Compression not triggered when below threshold

### Backward Compatibility

1. **Existing Flows Must Work**
   - [ ] Short conversations: No compression triggered (no overhead)
   - [ ] Compression is opportunistic, not required
   - [ ] Existing compression algorithm unchanged
   - [ ] No API changes

2. **No Breaking Changes**
   - [ ] MessageHistory interface unchanged
   - [ ] Agent.execute() signature unchanged
   - [ ] State structure unchanged
   - [ ] Event types unchanged

3. **Performance**
   - [ ] Compression only happens when needed (>40 messages)
   - [ ] One-time overhead during mission reset
   - [ ] Reduces token count for future LLM calls
   - [ ] Net performance benefit for long conversations

## Implementation Details

### File Changes

**File:** `capstone/agent_v2/agent.py`

**Location:** Lines 409-444 (mission reset block in Agent.execute)

**Changes:**
1. After clearing mission/todolist_id (line 421)
2. Before state save (line 425)
3. Add compression check and trigger
4. Add comprehensive logging

### Code Structure - Before (After Story 1)

```python
if should_reset_mission:
    # Logging (from Story 1)
    self.logger.info("resetting_mission_preserving_conversation", ...)
    
    # Clear mission and todolist
    self.mission = None
    self.state.pop("todolist_id", None)
    
    # Persist state changes
    await self.state_manager.save_state(session_id, self.state)
    
    # Emit event
    yield AgentEvent(...)
```

### Code Structure - After (With Compression)

```python
if should_reset_mission:
    # Logging (from Story 1)
    self.logger.info("resetting_mission_preserving_conversation", ...)
    
    # Clear mission and todolist
    self.mission = None
    self.state.pop("todolist_id", None)
    
    # NEW: Compression management
    message_count = len(self.message_history.messages)
    if message_count > self.message_history.SUMMARY_THRESHOLD:
        self.logger.info(
            "triggering_history_compression",
            session_id=session_id,
            message_count_before=message_count,
            threshold=self.message_history.SUMMARY_THRESHOLD
        )
        
        try:
            await self.message_history.compress_history_async()
            
            new_count = len(self.message_history.messages)
            self.logger.info(
                "history_compression_complete",
                session_id=session_id,
                message_count_before=message_count,
                message_count_after=new_count,
                messages_reduced=message_count - new_count
            )
        except Exception as e:
            self.logger.error(
                "history_compression_failed",
                session_id=session_id,
                error=str(e),
                message_count=message_count
            )
            # Continue execution despite failure
    
    # Persist state changes
    await self.state_manager.save_state(session_id, self.state)
    
    # Emit event
    yield AgentEvent(...)
```

### Testing Strategy

**Integration Tests Location:** `tests/integration/test_conversation_history_preservation.py` (extend)

**Test Cases:**

1. **Test: Long Conversation Triggers Compression**
   ```python
   async def test_long_conversation_triggers_compression():
       """Should trigger compression when message count exceeds threshold."""
       # Setup: RAG agent
       # Execute 45+ messages worth of queries (exceeds 40 threshold)
       # Trigger mission reset
       # Assert: compress_history_async() was called
       # Assert: Log message "triggering_history_compression" emitted
   ```

2. **Test: Compression Reduces Message Count**
   ```python
   async def test_compression_reduces_message_count():
       """Compression should reduce message count while preserving context."""
       # Setup: RAG agent with 45 messages
       # Trigger compression via mission reset
       # Assert: Message count reduced (< 45)
       # Assert: System prompt still present (first message)
       # Assert: Recent messages preserved
       # Assert: Summary message added
   ```

3. **Test: Context Preserved After Compression**
   ```python
   async def test_context_preserved_after_compression():
       """Essential context should be preserved after compression."""
       # Setup: Long conversation with important facts
       # Trigger compression
       # Execute new query referencing old context
       # Assert: Agent can still access key information
       # Assert: Conversation continues naturally
   ```

4. **Test: Short Conversations Skip Compression**
   ```python
   async def test_short_conversations_skip_compression():
       """Should not compress when message count below threshold."""
       # Setup: RAG agent with 20 messages (below 40)
       # Trigger mission reset
       # Assert: compress_history_async() NOT called
       # Assert: No compression logs emitted
       # Assert: Message count unchanged
   ```

5. **Test: Graceful Compression Failure**
   ```python
   async def test_graceful_compression_failure():
       """Should continue execution if compression fails."""
       # Setup: RAG agent with mock LLM that fails compression
       # Trigger compression (45+ messages)
       # Assert: Error logged "history_compression_failed"
       # Assert: Execution continues (doesn't crash)
       # Assert: Mission reset completes successfully
       # Assert: New query can still be processed
   ```

6. **Test: Compression at Mission Reset Boundary**
   ```python
   async def test_compression_at_reset_boundary():
       """Compression should happen during mission reset, not mid-query."""
       # Setup: RAG agent with 45 messages
       # Execute query (should NOT compress mid-query)
       # Complete query and start new query (triggers reset)
       # Assert: Compression happens during reset
       # Assert: Not during active query processing
   ```

## Dependencies

**Depends On:**
- Story 1: Remove MessageHistory Reset (conversation preservation)
- Story 2: System Prompt Decoupling (stable prompt architecture)

**Blocks:**
- None (final story in epic)

**Related Code:**
- `MessageHistory.compress_history_async()` (lines 102-140) - Existing compression
- `MessageHistory.SUMMARY_THRESHOLD` (line 75) - Existing constant
- `Agent.execute()` mission reset block - Integration point

## Definition of Done

- [ ] Compression check added to mission reset block
- [ ] Existing compress_history_async() method used
- [ ] Compression trigger uses SUMMARY_THRESHOLD constant
- [ ] Three log events implemented (trigger, success, failure)
- [ ] All 6 integration tests written and passing
- [ ] Graceful failure handling verified
- [ ] No regression in existing functionality
- [ ] Code review completed
- [ ] PEP8 compliant
- [ ] Documentation updated (inline comments)

## Testing Checklist

- [ ] Integration test: Long conversation triggers compression
- [ ] Integration test: Compression reduces message count
- [ ] Integration test: Context preserved after compression
- [ ] Integration test: Short conversations skip compression
- [ ] Integration test: Graceful compression failure
- [ ] Integration test: Compression at reset boundary
- [ ] Manual test: Run 50+ query conversation
- [ ] Manual test: Verify logs show compression events
- [ ] Manual test: Verify conversation continues after compression

## Dev Notes

### Context from Architecture

**Testing Standards:**
- Location: `tests/integration/test_conversation_history_preservation.py`
- Use pytest with async support
- Mock LLM service for compression tests
- Test both success and failure paths
- Verify logging output

**Relevant Source Tree:**
- `capstone/agent_v2/agent.py`
  - Lines 73-183: MessageHistory class
  - Lines 102-140: compress_history_async() method (existing)
  - Lines 75: SUMMARY_THRESHOLD constant (existing)
  - Lines 409-444: Mission reset block (integration point)

**Existing Infrastructure:**
MessageHistory already has built-in compression with:
- Automatic summarization using LLM
- Fallback to keeping recent messages on failure
- SUMMARY_THRESHOLD and MAX_MESSAGES constants

**This Story:** Just adds opportunistic trigger during mission reset.

### Previous Story Notes

From Story 1: MessageHistory preserved across resets
From Story 2: System prompt stable and mission-agnostic

**Build on this:** Now optimize long conversations with intelligent compression.

### Key Benefits

1. **Token Management:** Prevents hitting LLM token limits
2. **Performance:** Reduces context size for LLM calls
3. **User Experience:** Enables unlimited conversation length
4. **Cost Optimization:** Fewer tokens = lower API costs
5. **Graceful Degradation:** Works even if compression fails

### Testing

**Test Framework:** pytest with async support
**Integration Strategy:** Test with real MessageHistory, mock LLM
**Focus Areas:** Trigger logic, compression success, failure handling, threshold boundary

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

- **Optimization Story:** Enhances user experience for long conversations
- **Low Risk:** Uses existing, proven compression infrastructure
- **Non-Blocking:** Compression failure doesn't stop execution
- **Opportunistic:** Only compresses when needed (>40 messages)
- **Production Ready:** Leverages battle-tested algorithm
- **Observable:** Comprehensive logging for monitoring

## Compression Behavior Details

### When Compression Triggers

```
Message Count: 1-40   → No compression (below threshold)
Message Count: 41+    → Compression triggered at next mission reset
```

### What Gets Compressed

```
Before Compression (45 messages):
- System prompt (1)
- Old messages 1-40 (40) ← These get summarized
- Recent messages 41-45 (5) ← These stay as-is

After Compression (~15 messages):
- System prompt (1)
- Summary of messages 1-40 (1) ← Compressed!
- Recent messages 41-45 (5) ← Preserved
- Plus agent responses
```

### Token Savings Example

```
Before: 45 messages × ~200 tokens = ~9,000 tokens
After:  15 messages × ~200 tokens = ~3,000 tokens
Savings: ~6,000 tokens per LLM call (67% reduction!)
```

This enables:
- Longer conversations without hitting token limits
- Lower API costs (fewer tokens processed)
- Better performance (smaller context window)
- Preserved essential context via summary

## Edge Cases Handled

1. **Compression Fails:** System continues, logs error, keeps recent messages
2. **Below Threshold:** No compression attempted (no overhead)
3. **Exactly at Threshold:** No compression (uses > not >=)
4. **Empty History:** No compression (can't exceed threshold)
5. **LLM Unavailable:** Compression fails gracefully, execution continues

