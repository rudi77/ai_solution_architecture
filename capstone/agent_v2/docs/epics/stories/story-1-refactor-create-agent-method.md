# Story 1: Refactor Agent.create_agent() to Accept Tool List

**Epic:** Generalize Agent Factory Pattern - Brownfield Enhancement  
**Story ID:** AGENT-001  
**Story Type:** Refactoring  
**Priority:** High  
**Estimated Effort:** 3 hours

## User Story

**As a** developer maintaining the agent system  
**I want** the `Agent.create_agent()` method to accept a flexible list of tools  
**So that** I can create agents with different tool configurations without modifying the Agent class

## Background

Currently, `Agent.create_agent()` hardcodes a specific set of tools (WebSearchTool, WebFetchTool, PythonTool, GitHubTool, GitTool, FileReadTool, FileWriteTool, PowerShellTool, LLMTool). This makes it impossible to create agents with different tool sets without creating new specialized factory methods.

## Current Implementation

Location: `capstone/agent_v2/agent.py`, lines 860-915

```python
@staticmethod
def create_agent(name: str, description: str, system_prompt: str, 
                 mission: str, work_dir: str, llm) -> "Agent":
    tools = [
        WebSearchTool(),
        WebFetchTool(),
        PythonTool(),
        GitHubTool(),
        GitTool(),
        FileReadTool(),
        FileWriteTool(),
        PowerShellTool(),
        LLMTool(llm=llm),
    ]
    
    system_prompt = GENERIC_SYSTEM_PROMPT if system_prompt is None else system_prompt
    work_dir = Path(work_dir)
    work_dir.mkdir(exist_ok=True)
    
    todolist_dir = work_dir / "todolists"
    todolist_dir.mkdir(exist_ok=True)
    planner = TodoListManager(base_dir=todolist_dir)
    
    state_dir = work_dir / "states"
    state_dir.mkdir(exist_ok=True)
    state_manager = StateManager(state_dir=state_dir)
    
    return Agent(name, description, system_prompt, mission, tools, planner, state_manager, llm)
```

## Proposed Changes

### New Method Signature

```python
@staticmethod
def create_agent(
    name: str, 
    description: str, 
    system_prompt: Optional[str], 
    mission: Optional[str],
    tools: List[Tool],
    work_dir: str,
    llm
) -> "Agent":
```

### Key Changes

1. **Add `tools` parameter**: Accept `List[Tool]` as parameter instead of hardcoding
2. **Remove tool instantiation**: Delete the hardcoded tool list
3. **Keep directory setup logic**: Maintain existing directory and manager creation
4. **Keep defaults**: System prompt defaults to GENERIC_SYSTEM_PROMPT if None
5. **Type hints**: Ensure proper typing for all parameters

## Acceptance Criteria

### Functional Requirements

- [ ] Method signature updated to accept `tools: List[Tool]` parameter
- [ ] Hardcoded tool instantiation removed from method body
- [ ] Directory setup logic remains unchanged (work_dir, todolist_dir, state_dir creation)
- [ ] TodoListManager and StateManager creation remains unchanged
- [ ] System prompt defaults to GENERIC_SYSTEM_PROMPT when None
- [ ] Method returns Agent instance with provided tools
- [ ] Type hints are correct for all parameters

### Backward Compatibility

- [ ] Existing `create_rag_agent()` method continues to work
- [ ] Agent class constructor unchanged
- [ ] No breaking changes to Agent class interface

### Code Quality

- [ ] Docstring updated to reflect new signature and parameter
- [ ] Type hints follow existing codebase conventions
- [ ] Code follows existing formatting standards
- [ ] No linting errors introduced

## Technical Implementation Details

### Files to Modify

1. **`capstone/agent_v2/agent.py`**
   - Location: Lines 860-915
   - Update method signature
   - Remove tool instantiation code (lines 889-899)
   - Update docstring

### Implementation Steps

1. Update method signature:
   ```python
   def create_agent(
       name: str, 
       description: str, 
       system_prompt: Optional[str],
       mission: Optional[str],
       tools: List[Tool],  # NEW PARAMETER
       work_dir: str,
       llm
   ) -> "Agent":
   ```

2. Remove hardcoded tools (delete lines 889-899)

3. Update docstring to document new `tools` parameter:
   ```python
   """
   Creates an agent with the given parameters.

   Args:
       name: The name of the agent.
       description: The description of the agent.
       system_prompt: The system prompt for the agent (defaults to GENERIC_SYSTEM_PROMPT if None).
       mission: The mission for the agent.
       tools: List of Tool instances to equip the agent with.
       work_dir: The work directory for the agent.
       llm: The LLM instance for the agent.

   Returns:
       An Agent instance with the specified configuration.
   """
   ```

4. Keep all directory setup and manager creation code unchanged

### Edge Cases to Handle

- **Empty tool list**: Accept empty list (validation can happen in Agent constructor if needed)
- **None for system_prompt**: Keep existing default behavior
- **None for mission**: Keep existing behavior (allowed)
- **work_dir doesn't exist**: Keep existing behavior (create it)

## Testing Strategy

### Unit Tests

No new unit tests required - this is a refactoring. Existing behavior should be preserved.

### Integration Tests

- [ ] Run existing test suite: `test_rag_agent_integration.py`
- [ ] Verify `create_rag_agent()` still works (it calls the original constructor, not `create_agent()`)
- [ ] Manually test creating an agent with custom tool list

### Manual Testing

```python
from capstone.agent_v2.agent import Agent
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
import litellm

# Test with minimal tools
tools = [FileReadTool(), FileWriteTool()]
agent = Agent.create_agent(
    name="test_agent",
    description="Test agent with minimal tools",
    system_prompt=None,
    mission="Test mission",
    tools=tools,
    work_dir="./test_work",
    llm=litellm
)

assert len(agent.tools) == 2
assert agent.name == "test_agent"
```

### Regression Testing

- [ ] Existing CLI commands continue to work (they don't call `create_agent()` directly yet)
- [ ] Existing tests pass without modification
- [ ] No changes to agent runtime behavior

## Dependencies

### Depends On
- None (this is the first story)

### Blocks
- Story 2: Create Agent Factory Module (needs this refactored method)
- Story 3: YAML Configuration (needs this refactored method)

## Definition of Done

- [ ] Method signature updated with `tools: List[Tool]` parameter
- [ ] Hardcoded tool instantiation removed
- [ ] Docstring updated with accurate parameter descriptions
- [ ] Type hints are correct
- [ ] No linting errors in modified file
- [ ] Existing test suite passes (`pytest capstone/agent_v2/tests/`)
- [ ] `create_rag_agent()` method still works
- [ ] Code reviewed and follows project conventions
- [ ] Git commit with clear message

## Rollback Plan

If issues arise:
1. Git revert the commit
2. All existing functionality will be restored
3. No external dependencies or database changes to roll back

## Notes

- This story does NOT update any callers of `create_agent()` - that happens in Story 2
- `create_rag_agent()` is independent and continues to work
- Focus is purely on making the method more flexible
- No behavior changes to Agent class itself

## Verification Checklist

Before marking this story complete:

- [ ] Code compiles without errors
- [ ] No new linting errors introduced
- [ ] Existing test suite passes (100% pass rate)
- [ ] Manual test with custom tool list works
- [ ] Docstring is accurate and helpful
- [ ] Type hints are correct
- [ ] Code follows project style guide
- [ ] Git commit is clean and well-documented

---

**Created:** 2025-11-11  
**Status:** Ready for Development  
**Assignee:** TBD  
**Labels:** refactoring, agent-factory, technical-debt

