# Story: Implement PlannerTool - Brownfield Enhancement

## Story Title

Implement PlannerTool - Brownfield Enhancement

## User Story

As a **Developer**,
I want **a `PlannerTool` that allows the LLM to manage its own plan**,
So that **we can remove the rigid `TodoListManager` and enable dynamic agent behavior.**

## Story Context

**Existing System Integration:**
- Integrates with: `capstone/agent_v2/tools/` (as a new tool)
- Technology: Python 3.x, Pydantic, `ToolProtocol`
- Follows pattern: Existing `Tool` implementation (e.g., `WebSearchTool`, `FileReadTool`)
- Touch points: `agent.py` (will consume this tool later), `statemanager.py` (persistence)

## Acceptance Criteria

**Functional Requirements:**
1. Create `PlannerTool` class in `capstone/agent_v2/tools/planner_tool.py` implementing `ToolProtocol`.
2. Implement `create_plan(tasks: List[str])` action:
   - Validates list is not empty.
   - Stores tasks in internal state.
   - Returns confirmation message.
3. Implement `mark_done(step_index: int)` action:
   - Marks specific step as completed.
   - Returns updated status string.
   - Handles out-of-bounds errors gracefully.
4. Implement `read_plan()` action:
   - Returns formatted string representation of the plan (e.g., `[x] Step 1\n[ ] Step 2`).
   - Returns "No plan active" if empty.
5. Implement `update_plan(add_steps: List[str] = None, remove_indices: List[int] = None)`:
   - Allows dynamic modification of the plan.

**Integration Requirements:**
6. Tool state (current plan) must be serializable for `StateManager`.
7. New tool must follow `ToolProtocol` strict signature.
8. Unit tests must verify all actions.

**Quality Requirements:**
9. Code coverage > 80% for the new class.
10. Type hints and docstrings for all methods.

## Technical Notes

- **Integration Approach:** The tool will be standalone first, then integrated into `LeanAgent` in Story 2.
- **State Management:** The tool needs an internal `data` or `state` dictionary that can be extracted and restored.
- **Output Format:** `read_plan` output is critical as it will be injected into the System Prompt. Format should be concise Markdown.

## Definition of Done

- [x] `PlannerTool` class implemented and tested.
- [x] All actions (`create`, `mark_done`, `read`, `update`) functioning.
- [x] State serialization works.
- [x] Unit tests passing.
- [x] Linter checks pass (`ruff`).

## Dev Agent Record

### File List

| File | Status |
|------|--------|
| `capstone/agent_v2/tools/planner_tool.py` | Created |
| `capstone/agent_v2/tests/test_planner_tool.py` | Created |

### Change Log

| Date | Change |
|------|--------|
| 2025-12-04 | Implemented `PlannerTool` with `create_plan`, `mark_done`, `read_plan`, `update_plan` actions |
| 2025-12-04 | Added 26 unit tests achieving 98% coverage |

### Completion Notes

- Implementation follows existing `Tool` base class pattern from `tool.py`
- State serialization via `get_state()`/`set_state()` for `StateManager` integration
- Output format uses standard Markdown task list syntax (`[x]`/`[ ]`) for LLM clarity
- All acceptance criteria met

### Agent Model Used

Claude Opus 4.5 (via Cursor)

### Status

**Ready for Review**

## Risk and Compatibility Check

**Minimal Risk Assessment:**
- **Primary Risk:** Format of `read_plan` confuses the LLM.
- **Mitigation:** Stick to standard Markdown task list syntax (`- [ ] Task`).
- **Rollback:** Delete the file; no dependencies yet.

**Compatibility Verification:**
- [x] No breaking changes to existing APIs
- [x] No database changes
- [x] N/A UI changes
- [x] Performance impact negligible

## QA Results

### Review Date: 2025-12-04

### Reviewed By: Quinn (Test Architect)

### Code Quality Assessment

**Overall Assessment: EXCELLENT**

The implementation demonstrates exemplary adherence to established patterns and best practices. The `PlannerTool` class follows the `Tool` base class pattern consistently, with clean separation of concerns and well-structured action handlers. Code is self-documenting with comprehensive docstrings and type hints throughout.

**Strengths:**
- Clean action-based design pattern (action dispatch via `action_map`)
- Proper state encapsulation with defensive copying (`dict(self._state)`)
- Comprehensive error handling with descriptive messages
- Consistent return format (`{"success": bool, ...}`)
- Excellent testability through isolated action methods

**Minor Observations:**
- Line 238 in `_format_plan()` is uncovered (edge case handling) - acceptable given 98% coverage
- Action validation could be enhanced with enum type, but current string-based approach is pragmatic

### Refactoring Performed

**No refactoring required.** Code quality is excellent and follows established patterns. The implementation is production-ready.

### Compliance Check

- **Coding Standards**: ✓ Excellent adherence to PEP8, type hints, docstrings
- **Project Structure**: ✓ Follows `tools/` directory pattern, test structure matches conventions
- **Testing Strategy**: ✓ Comprehensive unit test suite (26 tests), 98% coverage exceeds requirement
- **All ACs Met**: ✓ All 10 acceptance criteria fully implemented and validated

### Requirements Traceability

**Complete Coverage Mapping:**

| AC | Requirement | Test Coverage | Status |
|----|-------------|---------------|--------|
| 1 | PlannerTool class implementing ToolProtocol | `TestPlannerToolMetadata` (3 tests) | ✓ PASS |
| 2 | `create_plan` action with validation | `TestPlannerToolCreatePlan` (4 tests) | ✓ PASS |
| 3 | `mark_done` action with error handling | `TestPlannerToolMarkDone` (5 tests) | ✓ PASS |
| 4 | `read_plan` action with formatting | `TestPlannerToolReadPlan` (3 tests) | ✓ PASS |
| 5 | `update_plan` dynamic modification | `TestPlannerToolUpdatePlan` (5 tests) | ✓ PASS |
| 6 | State serialization for StateManager | `TestPlannerToolStateSerialization` (5 tests) | ✓ PASS |
| 7 | ToolProtocol strict signature compliance | `TestPlannerToolMetadata.test_parameters_schema_structure` | ✓ PASS |
| 8 | Unit tests verify all actions | All 26 tests passing | ✓ PASS |
| 9 | Code coverage >80% | 98% achieved | ✓ PASS |
| 10 | Type hints and docstrings | All methods documented | ✓ PASS |

**Given-When-Then Test Patterns:**
- **Given** empty PlannerTool, **When** create_plan with valid tasks, **Then** plan created successfully
- **Given** plan with tasks, **When** mark_done with valid index, **Then** task marked complete
- **Given** plan with tasks, **When** mark_done with invalid index, **Then** error returned gracefully
- **Given** plan with mixed status, **When** read_plan, **Then** formatted Markdown returned
- **Given** plan, **When** update_plan with add/remove, **Then** plan modified correctly
- **Given** PlannerTool with state, **When** get_state/set_state roundtrip, **Then** state preserved

### Test Architecture Assessment

**Test Coverage: 98% (64 statements, 1 missed)**

**Test Organization: EXCELLENT**
- Logical grouping by action (CreatePlan, MarkDone, ReadPlan, UpdatePlan)
- Separate test classes for state serialization and metadata
- Edge case coverage comprehensive (empty lists, None values, out-of-bounds, invalid actions)
- Test naming follows descriptive pattern (`test_<action>_<scenario>`)

**Test Quality:**
- All tests use async/await correctly
- Assertions are clear and specific
- Test data is minimal and focused
- No test interdependencies (each test is isolated)

**Coverage Gaps:**
- Line 238 (`_format_plan`): Edge case for empty tasks list - acceptable given comprehensive test coverage

### Security Review

**Status: PASS**

- No authentication/authorization concerns (internal tool)
- No input validation vulnerabilities (type checking present)
- No data exposure risks (state stored internally)
- No injection vulnerabilities (no external data sources)
- State serialization is safe (dict-based, no pickle concerns)

### Performance Considerations

**Status: PASS**

- **Computational Complexity**: O(n) for plan operations (n = number of tasks) - optimal
- **Memory Overhead**: Minimal - single dict with list of task dicts
- **State Serialization**: Efficient dict operations, no deep copying overhead
- **Action Dispatch**: O(1) lookup via action_map dictionary
- **Format Plan**: Single pass through tasks list - efficient

**Performance Notes:**
- No performance concerns identified
- Tool is lightweight and suitable for frequent calls
- State operations are efficient for typical plan sizes (<100 tasks)

### Non-Functional Requirements Validation

**Security**: PASS (100/100)
- No security concerns identified
- Type safety enforced via Optional types
- No external data sources

**Performance**: PASS (100/100)
- Optimal O(n) complexity for all operations
- Minimal memory footprint
- No performance bottlenecks

**Reliability**: PASS (100/100)
- Comprehensive error handling
- Graceful degradation (returns error dicts, doesn't raise exceptions)
- State persistence tested via roundtrip tests
- Edge cases handled (empty plans, invalid indices, None values)

**Maintainability**: PASS (95/100)
- Excellent code clarity and structure
- Comprehensive docstrings
- Self-documenting method names
- Test suite serves as living documentation
- Minor: Could benefit from action enum type for type safety

### Testability Evaluation

**Controllability: EXCELLENT**
- All inputs controllable via action parameters
- State can be injected via constructor or `set_state()`
- No external dependencies (pure Python logic)

**Observability: EXCELLENT**
- All actions return structured dicts with `success` flag
- Error messages are descriptive and actionable
- Plan state observable via `read_plan()` and `get_state()`

**Debuggability: EXCELLENT**
- Clear error messages with context (e.g., "step_index 5 out of bounds (0-2)")
- Action-based design makes it easy to trace execution flow
- Test failures provide clear indication of what went wrong

### Technical Debt Identification

**No technical debt introduced.**

**Future Considerations:**
- Consider using `Enum` for action types instead of string literals (low priority)
- Consider adding plan validation (e.g., max task count) if needed in future (not required now)
- Consider adding plan metadata (created_at, updated_at) if needed for Story 2 integration

### Improvements Checklist

- [x] Verified all acceptance criteria met
- [x] Validated test coverage exceeds 80% requirement (98% achieved)
- [x] Confirmed code follows Tool base class pattern
- [x] Verified state serialization works correctly
- [x] Confirmed error handling is comprehensive
- [x] Validated type hints and docstrings present
- [ ] Consider action enum type for enhanced type safety (future enhancement, not blocking)

### Files Modified During Review

**No files modified.** Implementation is production-ready as delivered.

### Gate Status

**Gate: PASS** → `docs/qa/gates/lean-react-transition-epic.1-implement-planner-tool.yml`

**Quality Score: 98/100**

**Risk Profile:** Very Low Risk (Total Risk Score: 4/40)
- Breaking Changes: 1 (probability) × 1 (impact) = 1
- Integration Issues: 1 × 2 = 2
- LLM Confusion: 1 × 1 = 1

### Recommended Status

**✓ Ready for Done**

All acceptance criteria met, comprehensive test coverage, excellent code quality, zero technical debt. This story is production-ready and serves as a solid foundation for Story 2 (LeanAgent integration).

