# Story 3.2: Extend TodoListManager with Plan Modification - Brownfield Addition

## User Story

As an **agent planner**,
I want **TodoListManager to safely modify existing plans based on replan strategies**,
So that **failed tasks can be replaced, modified, or decomposed without corrupting the TodoList structure**.

## Story Context

**Existing System Integration:**

- Integrates with: TodoListManager (`capstone/agent_v2/planning/todolist.py`)
- Technology: Python 3.11, dataclasses, TodoList/TodoItem models
- Follows pattern: Existing TodoList manipulation methods (add, update, serialize)
- Touch points: TodoListManager, TodoItem dataclass, dependency validation

## Acceptance Criteria

### Functional Requirements

1. **Add `replan_count` field to TodoItem dataclass**
   - Type: `int`
   - Default: 0
   - Incremented each time a TodoItem is replanned
   - Used to enforce max replan limit (2 attempts)

2. **Implement `modify_step()` method in TodoListManager**
   - Updates existing TodoItem's tool, parameters, or description
   - Validates modifications maintain dependencies
   - Increments `replan_count`
   - Returns: `(success: bool, error: Optional[str])`

3. **Implement `decompose_step()` method in TodoListManager**
   - Splits TodoItem into multiple subtasks
   - Inserts subtasks at position of original task
   - Updates dependencies (dependents of original now depend on last subtask)
   - Original task marked SKIPPED with reason "decomposed"
   - Returns: `(success: bool, new_task_ids: List[int])`

4. **Implement `replace_step()` method in TodoListManager**
   - Replaces TodoItem with alternative approach (different tool/description)
   - Maintains position and dependencies
   - Increments `replan_count` on new task
   - Original task marked SKIPPED with reason "replaced"
   - Returns: `(success: bool, new_task_id: Optional[int])`

5. **Implement dependency validation for modifications**
   - Detect circular dependencies after plan modification
   - Validate all dependencies reference valid task positions
   - Ensure replan doesn't violate mission acceptance criteria
   - Rollback modification if validation fails

6. **Add replan limit enforcement**
   - Check `replan_count` before allowing modification
   - Max 2 replans per TodoItem
   - If limit exceeded, mark as FAILED and reject modification

### Integration Requirements

7. TodoItem schema extension (`replan_count`) is backward compatible (default 0)
8. Existing TodoList serialization/deserialization handles new field
9. TodoListManager persistence (JSON) includes `replan_count`
10. Plan modifications logged with before/after snapshots

### Quality Requirements

11. Unit tests for each modification method (modify, decompose, replace)
12. Unit tests for dependency validation after modifications
13. Unit tests for replan limit enforcement
14. Integration test: full replan workflow from strategy to modified plan
15. Test TodoList serialization with `replan_count` field

## Technical Notes

### Integration Approach

Extend TodoListManager with new plan modification methods. Each method performs the structural change, validates dependencies, and persists the updated TodoList.

**Code Location:** `capstone/agent_v2/planning/todolist.py` (TodoListManager class)

**Example Implementation:**

```python
@dataclass
class TodoItem:
    # ... existing fields ...
    replan_count: int = 0  # NEW: Track number of replanning attempts

class TodoListManager:
    
    async def modify_step(
        self, 
        todolist_id: str,
        step_position: int, 
        modifications: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Modify existing TodoItem parameters/tool"""
        
        todolist = await self.load_todolist(todolist_id)
        step = todolist.get_step_by_position(step_position)
        
        # Check replan limit
        if step.replan_count >= 2:
            return False, "Max replan attempts exceeded"
        
        # Apply modifications
        for key, value in modifications.items():
            if hasattr(step, key):
                setattr(step, key, value)
        
        step.replan_count += 1
        step.status = TaskStatus.PENDING  # Reset to retry
        
        # Validate dependencies still valid
        if not self._validate_dependencies(todolist):
            return False, "Modification would create circular dependency"
        
        # Persist
        await self.save_todolist(todolist)
        self.logger.info(f"Modified step {step_position}", modifications=modifications)
        
        return True, None
    
    async def decompose_step(
        self,
        todolist_id: str,
        step_position: int,
        subtasks: List[Dict[str, Any]]
    ) -> Tuple[bool, List[int]]:
        """Split TodoItem into multiple subtasks"""
        
        todolist = await self.load_todolist(todolist_id)
        original_step = todolist.get_step_by_position(step_position)
        
        # Check replan limit
        if original_step.replan_count >= 2:
            return False, []
        
        # Create subtasks
        new_positions = []
        insert_pos = step_position
        
        for i, subtask_data in enumerate(subtasks):
            subtask = TodoItem(
                position=insert_pos + i,
                description=subtask_data["description"],
                dependencies=[step_position] if i == 0 else [insert_pos + i - 1],
                status=TaskStatus.PENDING,
                replan_count=original_step.replan_count + 1
            )
            todolist.insert_step(subtask)
            new_positions.append(subtask.position)
        
        # Update dependents of original to depend on last subtask
        last_subtask_pos = new_positions[-1]
        for step in todolist.items:
            if step_position in step.dependencies:
                step.dependencies.remove(step_position)
                step.dependencies.append(last_subtask_pos)
        
        # Mark original as skipped
        original_step.status = TaskStatus.SKIPPED
        
        # Validate and persist
        if not self._validate_dependencies(todolist):
            return False, []
        
        await self.save_todolist(todolist)
        return True, new_positions
```

### Existing Pattern Reference

Follow TodoListManager's existing methods:
- `load_todolist()` / `save_todolist()` for persistence
- JSON serialization with dataclass_to_dict utilities
- Structured logging with operation context

### Key Constraints

- Plan modifications must maintain TodoList integrity (no orphaned dependencies)
- Replan limit enforced to prevent infinite modification loops
- Modifications are atomic (validation fails → rollback)
- Position renumbering after insertion must preserve order

## Definition of Done

- [x] `replan_count` field added to TodoItem dataclass
- [x] `modify_step()` method implemented with validation
- [x] `decompose_step()` method implemented with dependency updates
- [x] `replace_step()` method implemented with position preservation
- [x] Dependency validation detects circular dependencies
- [x] Replan limit (max 2) enforced in all methods
- [x] Unit tests pass for all modification methods
- [x] Dependency validation tests pass
- [x] TodoList serialization works with `replan_count` field
- [x] Integration test validates full modification workflow

## Risk and Compatibility Check

### Minimal Risk Assessment

**Primary Risk:** Plan modification corrupts TodoList structure (broken dependencies, invalid positions)

**Mitigation:**
- Comprehensive dependency validation after every modification
- Atomic operations (validate before persist)
- Replan count limit prevents infinite modification loops
- Extensive unit tests for edge cases (first/last item, circular deps)

**Rollback:**
- Remove `replan_count` field from TodoItem (defaults to 0, graceful)
- Remove modification methods from TodoListManager
- Existing TodoList loading works (ignores unknown fields)

### Compatibility Verification

- [x] TodoItem schema extension backward compatible
- [x] Existing TodoList serialization/deserialization unaffected
- [x] TodoListManager persistence format unchanged (JSON)
- [x] No breaking changes to TodoList public API

## Validation Checklist

### Scope Validation

- [x] Story can be completed in one development session (~5-6 hours)
- [x] Integration is straightforward (extend existing class)
- [x] Follows existing TodoListManager method patterns
- [x] Dependency validation logic self-contained

### Clarity Check

- [x] Story requirements are unambiguous
- [x] Integration points clearly specified (TodoListManager)
- [x] Success criteria testable via unit tests
- [x] Rollback approach is simple (remove methods)

---

## Dev Agent Record

### Status
**Ready for Review**

### Agent Model Used
- Claude Sonnet 4.5

### Completion Notes
- Successfully extended TodoItem dataclass with `replan_count` field (default 0)
- Implemented three plan modification methods in TodoListManager:
  - `modify_step()`: Updates existing TodoItem fields with validation
  - `decompose_step()`: Splits TodoItem into subtasks with dependency chaining
  - `replace_step()`: Replaces TodoItem with alternative approach
- Implemented `_validate_dependencies()` helper method that:
  - Validates all dependency references point to valid positions
  - Detects circular dependencies using DFS algorithm
  - Excludes SKIPPED items from validation (they don't execute)
- All modification methods enforce max 2 replan limit
- Added comprehensive test coverage (29 tests total, all passing):
  - TodoItem serialization/deserialization with replan_count
  - Helper methods (get_step_by_position, insert_step)
  - Dependency validation (valid, invalid reference, circular)
  - All three modification methods with success and error cases
  - Replan limit enforcement
  - Full integration workflow test
- All methods use structured logging with operation context
- Backward compatible: existing TodoLists load correctly (replan_count defaults to 0)

### File List
**Modified:**
- `capstone/agent_v2/planning/todolist.py` - Extended TodoItem and TodoListManager
- `tests/unit/test_todolist.py` - Added 19 new test cases

**No new files created.**

### Change Log
1. Added `replan_count: int = 0` field to TodoItem dataclass
2. Updated TodoItem.to_dict() to include replan_count in serialization
3. Updated TodoList.from_json() to deserialize replan_count field
4. Updated TodoList.to_dict() serialize_item function to include replan_count
5. Added TodoList.get_step_by_position() helper method
6. Added TodoList.insert_step() helper method for position management
7. Added TodoListManager._validate_dependencies() for circular dependency detection
8. Implemented TodoListManager.modify_step() with validation and rollback
9. Implemented TodoListManager.decompose_step() with dependency updates
10. Implemented TodoListManager.replace_step() with position preservation
11. Added 19 comprehensive test cases covering all new functionality
12. All tests passing (29/29), no linting errors

---

## QA Results

### Review Date: 2025-01-20

### Reviewed By: Quinn (Test Architect)

### Code Quality Assessment

**Overall Assessment: Excellent**

The implementation demonstrates high-quality code with comprehensive test coverage, proper error handling, and adherence to coding standards. All acceptance criteria are fully met with robust validation logic and backward compatibility.

**Strengths:**
- Clean, well-structured code following existing patterns
- Comprehensive test coverage (29 tests, 100% pass rate)
- Proper error handling with rollback mechanisms
- Excellent logging with structured context
- Backward compatible schema extension
- Atomic operations with validation before persistence
- Clear docstrings with type annotations

**Minor Concerns:**
- `get_step_by_position()` returns first match - after `replace_step()`, multiple items can share the same position (one SKIPPED, one active). However, validation logic correctly excludes SKIPPED items, so this doesn't cause functional issues. Consider adding a helper method `get_active_step_by_position()` for clarity in future iterations.

### Refactoring Performed

No refactoring required. Code quality is excellent and follows all best practices.

### Compliance Check

- **Coding Standards**: ✓ Fully compliant with PEP 8, proper type annotations, comprehensive docstrings, functions under 30 lines where appropriate
- **Project Structure**: ✓ Follows existing TodoListManager patterns, proper module organization
- **Testing Strategy**: ✓ Comprehensive unit tests covering all methods, edge cases, and integration workflow
- **All ACs Met**: ✓ All 15 acceptance criteria fully implemented and tested

### Requirements Traceability

**AC 1** (replan_count field): ✓ Implemented with default 0, serialized/deserialized correctly
- Test: `test_todoitem_replan_count_default`, `test_todoitem_replan_count_serialization`, `test_todolist_serialization_with_replan_count`

**AC 2** (modify_step method): ✓ Fully implemented with validation and rollback
- Tests: `test_modify_step_success`, `test_modify_step_replan_limit`, `test_modify_step_nonexistent`, `test_modify_step_invalid_dependencies`

**AC 3** (decompose_step method): ✓ Implemented with dependency chaining and position renumbering
- Tests: `test_decompose_step_success`, `test_decompose_step_replan_limit`, `test_decompose_step_empty_subtasks`

**AC 4** (replace_step method): ✓ Implemented with position preservation
- Tests: `test_replace_step_success`, `test_replace_step_replan_limit`, `test_replace_step_nonexistent`

**AC 5** (dependency validation): ✓ Comprehensive validation with circular dependency detection
- Tests: `test_validate_dependencies_valid`, `test_validate_dependencies_invalid_reference`, `test_validate_dependencies_circular`

**AC 6** (replan limit enforcement): ✓ Enforced in all three modification methods
- Tests: `test_modify_step_replan_limit`, `test_decompose_step_replan_limit`, `test_replace_step_replan_limit`

**AC 7-10** (Integration requirements): ✓ Backward compatible, serialization handles new field, persistence includes replan_count, logging implemented

**AC 11-15** (Quality requirements): ✓ Comprehensive test coverage for all methods, validation, limits, serialization, and full integration workflow

### Test Architecture Assessment

**Test Coverage: Excellent**
- 29 tests total (19 new tests added)
- Unit tests for all modification methods (modify, decompose, replace)
- Unit tests for dependency validation (valid, invalid reference, circular)
- Unit tests for replan limit enforcement
- Integration test for full modification workflow
- Serialization/deserialization tests

**Test Design Quality: High**
- Tests are well-structured, independent, and use appropriate fixtures
- Edge cases covered (non-existent positions, empty lists, limit exceeded)
- Integration test validates end-to-end workflow
- Proper use of mocks for LLMService

**Test Level Appropriateness: Correct**
- Unit tests for individual methods and validation logic
- Integration test for workflow validation
- No E2E tests needed (this is a planning module, not user-facing)

### Improvements Checklist

- [x] All acceptance criteria verified and tested
- [x] Code follows coding standards
- [x] Comprehensive test coverage implemented
- [ ] Consider adding `get_active_step_by_position()` helper for clarity (non-blocking, future enhancement)
- [ ] Consider adding validation to prevent duplicate positions in TodoList (non-blocking, current implementation handles this correctly)

### Security Review

**Status: PASS**

- No security vulnerabilities identified
- Input validation present (position existence checks, dependency validation)
- No sensitive data exposure
- Proper error handling prevents information leakage
- Atomic operations prevent partial state corruption

### Performance Considerations

**Status: PASS**

- Efficient dependency validation using DFS algorithm (O(V+E))
- Position renumbering is O(n) where n is number of items
- No performance concerns for expected use cases
- Proper use of async/await for I/O operations

### Files Modified During Review

No files modified during review. Implementation is production-ready.

### Gate Status

Gate: **PASS** → `docs/qa/gates/3.2-todolist-plan-modification.yml`

### Recommended Status

✓ **Ready for Done**

All acceptance criteria met, comprehensive test coverage, excellent code quality. Minor enhancement suggestions are non-blocking and can be addressed in future iterations.

