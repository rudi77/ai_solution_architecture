# Story 1.4: Implement Core Domain - TodoList Planning

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.4  
**Status**: Pending  
**Priority**: High  
**Estimated Points**: 3  
**Dependencies**: Story 1.2 (Protocol Interfaces)

---

## User Story

As a **developer**,  
I want **TodoList planning logic extracted into core domain**,  
so that **plan generation and task management are testable without persistence dependencies**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/core/domain/plan.py` with domain classes and logic
2. ✅ Extract from `capstone/agent_v2/planning/todolist.py`:
   - `TodoItem` dataclass (position, description, acceptance_criteria, dependencies, status, chosen_tool, execution_result)
   - `TodoList` dataclass (mission, items, created_at, updated_at)
   - `TaskStatus` enum (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
   - `PlanGenerator` class (LLM-based plan generation logic)
3. ✅ Refactor `PlanGenerator` to accept `llm_provider: LLMProviderProtocol` via constructor
4. ✅ Preserve all planning algorithms from Agent V2 (dependency validation, LLM prompts for plan generation)
5. ✅ Remove all persistence logic (file I/O, JSON serialization) - delegate to infrastructure layer
6. ✅ Create `validate_dependencies(plan)` method ensuring no circular dependencies
7. ✅ Unit tests with mocked LLM verify plan generation logic without actual LLM calls

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 planning continues to work independently
- **IV2: Integration Point Verification** - Generated plans match Agent V2 plan structure (same JSON schema when serialized)
- **IV3: Performance Impact Verification** - Plan validation completes in <100ms for plans with 20 tasks

---

## Technical Notes

**Domain Classes:**

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TodoItem:
    """Single task in a TodoList."""
    position: int
    description: str
    acceptance_criteria: List[str]
    dependencies: List[int] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    chosen_tool: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None

@dataclass
class TodoList:
    """Complete plan for a mission."""
    mission: str
    items: List[TodoItem]
    todolist_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

class PlanGenerator:
    """Generates TodoLists from mission descriptions using LLM."""
    
    def __init__(self, llm_provider: LLMProviderProtocol):
        self.llm_provider = llm_provider
    
    async def generate_plan(self, mission: str) -> TodoList:
        """Generate TodoList from mission description."""
        # Extract logic from agent_v2/planning/todolist.py
        ...
    
    def validate_dependencies(self, plan: TodoList) -> bool:
        """Validate no circular dependencies in plan."""
        ...
```

**Reference Files:**
- `capstone/agent_v2/planning/todolist.py` - Extract TodoItem, TodoList, PlanGenerator
- Keep LLM prompts for plan generation
- Remove `TodoListManager` class (persistence - goes to infrastructure)

**What to Extract vs. Leave:**
- ✅ Extract: Domain classes (TodoItem, TodoList, TaskStatus)
- ✅ Extract: Plan generation logic (LLM-based)
- ✅ Extract: Dependency validation
- ❌ Leave: File I/O, JSON serialization (goes to infrastructure/persistence)
- ❌ Leave: TodoListManager (becomes infrastructure adapter)

---

## Testing Strategy

```python
# tests/unit/core/test_plan.py
from unittest.mock import AsyncMock
from taskforce.core.domain.plan import PlanGenerator, TodoList

async def test_plan_generation():
    mock_llm = AsyncMock(spec=LLMProviderProtocol)
    mock_llm.complete.return_value = {
        "content": '{"items": [...]}'  # Mocked plan JSON
    }
    
    generator = PlanGenerator(llm_provider=mock_llm)
    plan = await generator.generate_plan("Create a web app")
    
    assert isinstance(plan, TodoList)
    assert len(plan.items) > 0
    assert all(item.status == TaskStatus.PENDING for item in plan.items)

def test_dependency_validation_no_cycles():
    plan = TodoList(mission="Test", items=[
        TodoItem(position=0, description="Task 1", dependencies=[]),
        TodoItem(position=1, description="Task 2", dependencies=[0]),
    ])
    
    generator = PlanGenerator(llm_provider=mock_llm)
    assert generator.validate_dependencies(plan) == True
```

---

## Definition of Done

- [ ] `plan.py` contains TodoItem, TodoList, TaskStatus, PlanGenerator
- [ ] All domain logic extracted from Agent V2
- [ ] Zero persistence code in domain layer
- [ ] Dependency validation logic implemented
- [ ] Unit tests achieve ≥90% coverage
- [ ] Unit tests use mocked LLM (no actual API calls)
- [ ] Dependency validation completes <100ms for 20-task plans
- [ ] Code review completed
- [ ] Code committed to version control

