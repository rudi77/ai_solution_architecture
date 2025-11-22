# Story 1.2: Define Core Protocol Interfaces

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.2  
**Status**: Pending  
**Priority**: Critical  
**Estimated Points**: 3  
**Dependencies**: Story 1.1 (Project Structure)

---

## User Story

As a **developer**,  
I want **protocol interfaces defined for all external dependencies**,  
so that **core domain logic can be implemented without infrastructure coupling**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/core/interfaces/state.py` with `StateManagerProtocol`:
   - Methods: `save_state(session_id, state_data)`, `load_state(session_id)`, `delete_state(session_id)`, `list_sessions()`
   - All methods return type-annotated values matching Agent V2 `statemanager.py` signatures
2. ✅ Create `taskforce/src/taskforce/core/interfaces/llm.py` with `LLMProviderProtocol`:
   - Methods: `complete(model, messages, **params)`, `generate(model, prompt, **params)`
   - Return types match Agent V2 `services/llm_service.py` public API
3. ✅ Create `taskforce/src/taskforce/core/interfaces/tools.py` with `ToolProtocol`:
   - Properties: `name`, `description`, `parameters_schema`
   - Methods: `execute(**params)`, `validate_parameters(params)`
   - Based on Agent V2 `tool.py` abstract base class
4. ✅ Create `taskforce/src/taskforce/core/interfaces/todolist.py` with `TodoListManagerProtocol`:
   - Methods: `create_plan(mission)`, `get_plan(todolist_id)`, `update_task_status(task_id, status)`, `save_plan(plan)`
   - Return types use TodoList/TodoItem dataclasses (to be defined in next story)
5. ✅ Add comprehensive docstrings to all protocols explaining contract expectations
6. ✅ All protocols use Python 3.11 Protocol class (from `typing`)
7. ✅ Type hints validated with mypy (zero type errors)

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 continues to function (no imports from taskforce yet)
- **IV2: Integration Point Verification** - Protocols can be imported and used in type hints without runtime errors
- **IV3: Performance Impact Verification** - N/A (interface definitions only)

---

## Technical Notes

**Protocol Example Structure:**

```python
from typing import Protocol, Dict, Any, List, Optional
from dataclasses import dataclass

class StateManagerProtocol(Protocol):
    """Protocol defining the contract for state persistence."""
    
    async def save_state(
        self, 
        session_id: str, 
        state_data: Dict[str, Any]
    ) -> None:
        """Save session state."""
        ...
    
    async def load_state(
        self, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load session state by ID."""
        ...
    
    async def delete_state(
        self, 
        session_id: str
    ) -> None:
        """Delete session state."""
        ...
    
    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        ...
```

**Reference Files:**
- `capstone/agent_v2/statemanager.py` - For StateManagerProtocol signatures
- `capstone/agent_v2/services/llm_service.py` - For LLMProviderProtocol signatures
- `capstone/agent_v2/tool.py` - For ToolProtocol signatures
- `capstone/agent_v2/planning/todolist.py` - For TodoListManagerProtocol signatures

---

## Definition of Done

- [ ] All four protocol files created with complete type hints
- [ ] Comprehensive docstrings explaining each protocol contract
- [ ] `mypy` passes with zero type errors
- [ ] Protocols can be imported without runtime errors
- [ ] Unit tests can create mock implementations of protocols
- [ ] Code review completed
- [ ] Code committed to version control

