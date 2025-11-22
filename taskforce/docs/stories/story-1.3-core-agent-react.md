# Story 1.3: Implement Core Domain - Agent ReAct Loop

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.3  
**Status**: Pending  
**Priority**: Critical  
**Estimated Points**: 5  
**Dependencies**: Story 1.2 (Protocol Interfaces)

---

## User Story

As a **developer**,  
I want **the ReAct execution loop extracted from Agent V2 into core domain**,  
so that **business logic is testable without infrastructure dependencies**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/core/domain/agent.py` with `Agent` class
2. ✅ Extract ReAct loop logic from `capstone/agent_v2/agent.py:Agent.execute()`:
   - Thought generation (LLM call for reasoning)
   - Action decision (tool selection or ask_user or complete)
   - Observation recording (tool execution result)
3. ✅ Refactor to accept dependencies via constructor injection:
   - `state_manager: StateManagerProtocol`
   - `llm_provider: LLMProviderProtocol`
   - `tools: List[ToolProtocol]`
   - `todolist_manager: TodoListManagerProtocol`
4. ✅ Create `execute(mission: str, session_id: str) -> ExecutionResult` method implementing ReAct loop
5. ✅ Preserve Agent V2 execution semantics (same loop termination conditions, same error handling)
6. ✅ Create dataclasses for domain events: `Thought`, `Action`, `Observation` in `core/domain/events.py`
7. ✅ Unit tests using protocol mocks verify ReAct logic without any I/O

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 remains operational (not yet using taskforce agent)
- **IV2: Integration Point Verification** - Unit tests verify identical ReAct behavior using mocked protocols compared to Agent V2 execution traces
- **IV3: Performance Impact Verification** - Unit tests complete in <1 second (pure in-memory logic)

---

## Technical Notes

**Agent Class Structure:**

```python
from dataclasses import dataclass
from typing import List
from taskforce.core.interfaces.state import StateManagerProtocol
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.core.interfaces.tools import ToolProtocol
from taskforce.core.interfaces.todolist import TodoListManagerProtocol

@dataclass
class ExecutionResult:
    """Result of agent execution."""
    session_id: str
    status: str  # completed, failed, pending
    final_message: str
    execution_history: List[Dict]

class Agent:
    """Core ReAct agent with protocol-based dependencies."""
    
    def __init__(
        self,
        state_manager: StateManagerProtocol,
        llm_provider: LLMProviderProtocol,
        tools: List[ToolProtocol],
        todolist_manager: TodoListManagerProtocol,
        system_prompt: str
    ):
        self.state_manager = state_manager
        self.llm_provider = llm_provider
        self.tools = {tool.name: tool for tool in tools}
        self.todolist_manager = todolist_manager
        self.system_prompt = system_prompt
    
    async def execute(
        self, 
        mission: str, 
        session_id: str
    ) -> ExecutionResult:
        """Execute ReAct loop for given mission."""
        # Extract ReAct loop logic from agent_v2/agent.py
        ...
```

**Reference Files:**
- `capstone/agent_v2/agent.py` - Lines 100-500 contain the ReAct loop
- Focus on `Agent.execute()` method and `MessageHistory` management

**Key Logic to Extract:**
- ReAct loop: while not done → thought → action → observation
- Tool selection and execution
- User interaction handling (ask_user)
- Loop termination conditions
- Error handling and retry logic

---

## Testing Strategy

**Unit Tests with Mocks:**
```python
# tests/unit/core/test_agent.py
from unittest.mock import AsyncMock
from taskforce.core.domain.agent import Agent

async def test_react_loop_basic_execution():
    # Mock all protocols
    mock_state_manager = AsyncMock(spec=StateManagerProtocol)
    mock_llm_provider = AsyncMock(spec=LLMProviderProtocol)
    mock_tools = [...]
    mock_todolist_manager = AsyncMock(spec=TodoListManagerProtocol)
    
    agent = Agent(
        state_manager=mock_state_manager,
        llm_provider=mock_llm_provider,
        tools=mock_tools,
        todolist_manager=mock_todolist_manager,
        system_prompt="Test prompt"
    )
    
    result = await agent.execute("Test mission", "test-session-123")
    
    assert result.status == "completed"
    assert mock_llm_provider.complete.called
```

---

## Definition of Done

- [ ] `Agent` class implemented in `core/domain/agent.py`
- [ ] ReAct loop logic extracted from Agent V2
- [ ] All dependencies injected via protocols (zero infrastructure imports)
- [ ] `events.py` contains Thought, Action, Observation dataclasses
- [ ] Unit tests achieve ≥90% coverage of ReAct logic
- [ ] Unit tests use only protocol mocks (no I/O)
- [ ] Tests complete in <1 second
- [ ] Code review completed
- [ ] Code committed to version control

