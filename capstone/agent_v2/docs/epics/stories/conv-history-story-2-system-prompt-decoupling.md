# Story 2: System Prompt Decoupling from Mission

**Epic:** Conversation History Preservation - Brownfield Enhancement  
**Story ID:** CONV-HIST-002  
**Status:** Draft  
**Priority:** High  
**Estimated Effort:** 1 day  

## Story Description

Decouple mission from system prompt to maintain stable LLM context across multiple queries. This architectural improvement treats each user query as a natural conversation message rather than embedding the mission in the system prompt, enabling better conversational flow and eliminating confusion when missions change.

## User Story

**As a** RAG agent developer  
**I want** system prompts to be mission-agnostic  
**So that** the LLM maintains stable context across multiple queries without mission-specific text causing confusion

## Acceptance Criteria

### Functional Requirements

1. **System Prompt Template Storage**
   - [ ] Store base system prompt template in `Agent.__init__()` as instance variable
   - [ ] Template contains: role, tools, behavior guidelines (no mission)
   - [ ] Use `self.system_prompt_template` for rebuilding prompts if needed
   - [ ] Keep original `system_prompt` parameter for backward compatibility

2. **Mission-Agnostic System Prompt Generation**
   - [ ] Update `build_system_prompt()` to accept `mission=None`
   - [ ] When mission is None: Generate prompt without mission-specific text
   - [ ] System prompt contains only: agent role, available tools, behavior guidelines
   - [ ] No query-specific information embedded in system prompt

3. **User Queries as Conversation Messages**
   - [ ] User queries treated as normal `user` role messages in conversation
   - [ ] Queries added to MessageHistory naturally (not embedded in system prompt)
   - [ ] LLM sees queries in natural chronological order
   - [ ] Mission stored internally but not in system prompt

4. **MessageHistory Initialization**
   - [ ] Update MessageHistory init in `Agent.__init__()` (line 348)
   - [ ] Pass mission-agnostic system prompt to MessageHistory
   - [ ] First message in history is stable system prompt
   - [ ] System prompt remains unchanged across mission resets

### Technical Requirements

1. **Code Locations**
   - Modify: `capstone/agent_v2/agent.py`
     - `Agent.__init__()` (line 336-353) - Store template, update MessageHistory init
   - Modify: `capstone/agent_v2/prompts/rag_system_prompt.py` (or equivalent)
     - `build_system_prompt()` function - Support mission=None
   - No changes to: MessageHistory class interface

2. **Implementation Pattern - Agent.__init__()**
   ```python
   def __init__(
       self,
       name: str,
       mission: Optional[str],
       system_prompt: str,  # Base template without mission
       tools: List[BaseTool],
       todo_list_manager: TodoListManager,
       state_manager: StateManager,
       llm_service: LLMService,
   ):
       self.name = name
       self.mission = mission
       # NEW: Store system prompt template for potential rebuilding
       self.system_prompt_template = system_prompt
       self.tools = tools
       self.tools_description = self._get_tools_description()
       self.tools_schema = self._get_tools_schema()
       self.todo_list_manager = todo_list_manager
       self.state_manager = state_manager
       self.llm_service = llm_service
       self.state = None
       
       # UPDATED: Initialize MessageHistory with mission-agnostic prompt
       self.message_history = MessageHistory(
           build_system_prompt(
               system_prompt,
               None,  # No mission in system prompt
               self.tools_description
           ),
           llm_service
       )
       self.logger = structlog.get_logger().bind(agent=name)
   ```

3. **Implementation Pattern - build_system_prompt()**
   ```python
   def build_system_prompt(
       base_prompt: str,
       mission: Optional[str],  # Can be None
       tools_description: str
   ) -> str:
       """
       Build system prompt for the agent.
       
       Args:
           base_prompt: Base system prompt template (role, behavior)
           mission: Optional mission statement (None for mission-agnostic)
           tools_description: Available tools description
           
       Returns:
           Complete system prompt
       """
       # Start with base prompt (role, behavior guidelines)
       prompt_parts = [base_prompt]
       
       # Add tools description
       prompt_parts.append(f"\n\n## Available Tools\n\n{tools_description}")
       
       # Only add mission if provided (backward compatibility)
       if mission:
           prompt_parts.append(f"\n\n## Current Mission\n\n{mission}")
       
       return "\n".join(prompt_parts)
   ```

4. **Type Annotations**
   - [ ] `self.system_prompt_template: str` in Agent
   - [ ] `mission: Optional[str]` in build_system_prompt()
   - [ ] Maintain existing type annotations

5. **Error Handling**
   - [ ] Handle None mission gracefully in build_system_prompt()
   - [ ] Ensure backward compatibility when mission IS provided
   - [ ] No crashes if mission changes during execution

### Code Quality Requirements

1. **Python Best Practices**
   - [ ] PEP8 compliant formatting
   - [ ] Full type annotations (use Optional[str])
   - [ ] Updated docstrings for modified functions
   - [ ] Clear comments explaining architectural change

2. **Logging Best Practices**
   - [ ] Log system prompt initialization mode (with/without mission)
   - [ ] Use structlog with context
   - [ ] Log if mission changes (future use)

3. **Testing**
   - [ ] Unit test: build_system_prompt() with mission=None
   - [ ] Unit test: build_system_prompt() with mission (backward compat)
   - [ ] Integration test: System prompt stable across mission resets
   - [ ] Integration test: Queries appear as user messages in history
   - [ ] Integration test: Conversational flow with mission-agnostic prompts

### Backward Compatibility

1. **Existing Flows Must Work**
   - [ ] Single-mission agents with mission in __init__: Still work
   - [ ] Agents that provide mission parameter: Still work
   - [ ] build_system_prompt() with mission parameter: Still works
   - [ ] No breaking changes to agent creation

2. **API Compatibility**
   - [ ] `Agent.__init__()` signature unchanged (mission still accepted)
   - [ ] `build_system_prompt()` signature accepts Optional[str] for mission
   - [ ] MessageHistory interface unchanged
   - [ ] State structure unchanged

3. **Migration Path**
   - [ ] Existing agents continue to work without changes
   - [ ] New agents can use mission-agnostic pattern
   - [ ] Gradual migration supported

## Implementation Details

### File Changes

**File 1:** `capstone/agent_v2/agent.py`

**Changes:**
1. Add `self.system_prompt_template = system_prompt` in `__init__()` (after line 340)
2. Update MessageHistory initialization to use mission-agnostic prompt (line 348-351)

**File 2:** `capstone/agent_v2/prompts/rag_system_prompt.py` (or wherever build_system_prompt is)

**Changes:**
1. Update `build_system_prompt()` signature: `mission: Optional[str]`
2. Add conditional logic to only include mission section if mission provided
3. Update docstring to document mission=None behavior

### Code Structure - Before

```python
# Current build_system_prompt (approximate):
def build_system_prompt(base_prompt: str, mission: str, tools_desc: str) -> str:
    """Build system prompt with mission embedded."""
    return f"{base_prompt}\n\n## Mission\n{mission}\n\n## Tools\n{tools_desc}"

# Current Agent.__init__:
self.message_history = MessageHistory(
    build_system_prompt(system_prompt, mission, self.tools_description),
    llm_service
)
# Problem: Mission embedded in system prompt, changes when mission resets
```

### Code Structure - After

```python
# Updated build_system_prompt:
def build_system_prompt(
    base_prompt: str, 
    mission: Optional[str],  # Can be None
    tools_desc: str
) -> str:
    """
    Build system prompt for agent.
    
    Args:
        base_prompt: Base system prompt with role and behavior
        mission: Optional mission statement (None for mission-agnostic)
        tools_desc: Available tools description
        
    Returns:
        Complete system prompt
    """
    prompt = f"{base_prompt}\n\n## Available Tools\n\n{tools_desc}"
    
    # Only add mission if provided (backward compatibility)
    if mission:
        prompt += f"\n\n## Current Mission\n\n{mission}"
    
    return prompt

# Updated Agent.__init__:
def __init__(self, ..., system_prompt: str, ...):
    # Store template for potential rebuilding
    self.system_prompt_template = system_prompt
    
    # ... other initialization ...
    
    # Initialize with mission-agnostic system prompt
    self.message_history = MessageHistory(
        build_system_prompt(
            system_prompt,
            None,  # Mission-agnostic
            self.tools_description
        ),
        llm_service
    )
```

### Testing Strategy

**Unit Tests Location:** `tests/unit/test_system_prompt.py` (new file)

**Integration Tests Location:** `tests/integration/test_conversation_history_preservation.py` (extend)

**Test Cases:**

1. **Unit Test: Mission-Agnostic Prompt Generation**
   ```python
   def test_build_system_prompt_without_mission():
       """Should generate prompt without mission section when mission=None."""
       # Setup: Base prompt and tools description
       # Action: Call build_system_prompt(base, None, tools)
       # Assert: Result contains base prompt and tools
       # Assert: Result does NOT contain mission section
       # Assert: Result is valid system prompt
   ```

2. **Unit Test: Backward Compatible with Mission**
   ```python
   def test_build_system_prompt_with_mission():
       """Should include mission section when mission provided."""
       # Setup: Base prompt, mission, tools
       # Action: Call build_system_prompt(base, mission, tools)
       # Assert: Result contains base prompt, mission, and tools
       # Assert: Mission section properly formatted
   ```

3. **Integration Test: System Prompt Stability**
   ```python
   async def test_system_prompt_stable_across_resets():
       """System prompt should not change when mission resets."""
       # Setup: RAG agent
       # Get initial system prompt (first message in history)
       # Query 1: Execute and complete
       # Query 2: Execute (triggers reset)
       # Assert: System prompt unchanged (still first message)
       # Assert: Same system prompt content before and after reset
   ```

4. **Integration Test: Queries as User Messages**
   ```python
   async def test_queries_appear_as_user_messages():
       """User queries should appear as natural conversation messages."""
       # Setup: RAG agent
       # Query 1: "What is X?"
       # Assert: Query added as {"role": "user", "content": "What is X?"}
       # Query 2: "What is Y?"
       # Assert: Both queries in message history as user messages
       # Assert: Natural conversation flow in history
   ```

5. **Integration Test: Mission-Agnostic Conversational Flow**
   ```python
   async def test_conversational_flow_with_stable_prompt():
       """Agent should handle multi-turn conversation with stable system prompt."""
       # Setup: RAG agent with mission-agnostic prompt
       # Execute 3 different queries
       # Assert: All queries processed correctly
       # Assert: System prompt unchanged
       # Assert: Each query visible in history as user message
       # Assert: LLM responses appropriate for each query
   ```

## Dependencies

**Depends On:**
- Story 1: Remove MessageHistory Reset (conversation preservation bug fix)

**Blocks:**
- Story 3: Automatic Compression (builds on stable prompt architecture)

**Related Code:**
- `build_system_prompt()` function - System prompt construction
- `Agent.__init__()` - MessageHistory initialization
- `MessageHistory` class - Conversation management
- `Agent.execute()` - Mission handling

## Definition of Done

- [ ] `system_prompt_template` stored in Agent.__init__()
- [ ] `build_system_prompt()` supports mission=None
- [ ] MessageHistory initialized with mission-agnostic prompt
- [ ] All 5 tests (2 unit, 3 integration) written and passing
- [ ] System prompt remains stable across mission resets
- [ ] Backward compatibility maintained (agents with mission still work)
- [ ] No regression in existing functionality
- [ ] Code review completed
- [ ] Full type annotations
- [ ] PEP8 compliant
- [ ] Documentation updated (docstrings)

## Testing Checklist

- [ ] Unit test: Mission-agnostic prompt generation
- [ ] Unit test: Backward compatible with mission
- [ ] Integration test: System prompt stability across resets
- [ ] Integration test: Queries as user messages
- [ ] Integration test: Conversational flow with stable prompt
- [ ] Manual test: Create agent with mission=None works
- [ ] Manual test: Create agent with mission works (backward compat)
- [ ] Manual test: RAG CLI conversation flow natural

## Dev Notes

### Context from Architecture

**Testing Standards:**
- Unit tests: `tests/unit/test_system_prompt.py`
- Integration tests: Extend `tests/integration/test_conversation_history_preservation.py`
- Use pytest with async support where needed
- Mock LLM service for integration tests
- Test both new pattern and backward compatibility

**Relevant Source Tree:**
- `capstone/agent_v2/agent.py`
  - Lines 336-353: Agent.__init__() method
  - Lines 348-351: MessageHistory initialization (target)
- `capstone/agent_v2/prompts/rag_system_prompt.py` (or equivalent)
  - `build_system_prompt()` function (target)

**Design Pattern:**
This follows the "Template Method" pattern where the base system prompt is a template that remains stable, and mission-specific content is optional/dynamic.

### Previous Story Notes

From Story 1 (Remove History Reset):
- MessageHistory now preserved across mission resets
- Conversation context flows naturally
- TodoList still resets independently

**Build on this:** Now make system prompt stable so LLM context is clean and mission changes don't confuse the model.

### Key Architectural Benefit

**Before:** System prompt changes with each mission, confusing the LLM
- System: "Your mission is X"
- User: Query about X
- System changes to: "Your mission is Y"  ← Confusing!

**After:** System prompt stays stable, missions are just natural queries
- System: "You are a RAG agent with these tools..."
- User: Query about X
- Agent: Response about X
- User: Query about Y  ← Natural conversation flow
- Agent: Response about Y

### Testing

**Test Framework:** pytest
**Unit Test Strategy:** Test build_system_prompt() in isolation
**Integration Test Strategy:** Test full agent conversation flow
**Backward Compatibility:** Test both mission=None and mission="..." patterns

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

- **Architectural Improvement**: Cleaner separation of concerns
- **Backward Compatible**: Existing agents still work
- **Foundation for Future**: Enables better conversation management
- **No Breaking Changes**: Optional enhancement, not required
- **Clean Design**: System prompt is truly "system" level, not query level
- **Better LLM Context**: No confusion from changing mission statements

## Migration Guide for Existing Code

**For New Agents (Recommended):**
```python
agent = create_rag_agent(
    session_id=session_id,
    user_context=user_context
    # mission is set dynamically in execute(), not __init__()
)
```

**For Existing Agents (Still Supported):**
```python
agent = Agent(
    name="My Agent",
    mission="Specific mission",  # Still works!
    system_prompt=base_prompt,
    # ... other params
)
# Mission will be included in system prompt (backward compatible)
```

**Gradual Migration:** Teams can migrate at their own pace. Both patterns supported.

