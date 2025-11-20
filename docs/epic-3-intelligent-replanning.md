# Epic 3: Intelligent Replanning (Self-Healing) - Brownfield Enhancement

## Epic Goal

Implement autonomous plan adaptation that allows the agent to recover from tool failures by generating alternative strategies, rather than simply marking steps as FAILED or SKIPPED, significantly improving mission completion rates.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- ReAct agent with TodoList-based planning (TodoListManager, TodoList, TodoItem)
- Task execution with retry logic (max_attempts=3 in execute_safe)
- Failure handling: steps marked FAILED after retries, agent continues or aborts
- `_replan()` method exists but contains only `TODO: Implement intelligent replanning`
- Action types: tool_call, ask_user, complete, replan (partially implemented)

**Technology stack:**
- Python 3.11 with asyncio
- LLM-based planning via TodoListManager (`capstone/agent_v2/planning/todolist.py`)
- Agent orchestration with MessageHistory and LLMService
- TaskStatus enum: PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED

**Integration points:**
- Agent's `_execute_action()` failure handling path
- TodoListManager for plan modification
- LLMService for generating replan strategies
- MessageHistory for providing failure context to LLM

### Enhancement Details

**What's being added/changed:**
- Implement intelligent replanning in Agent's `_replan()` method
- Add replan strategy generation via LLM (analyze failure → suggest alternatives)
- Support three replan strategies:
  - **Retry with modified parameters** (different tool arguments)
  - **Tool substitution** (use alternative tool for same goal)
  - **Task decomposition** (split failed step into smaller substeps)
- Add failure context accumulation for LLM decision-making
- Extend TodoListManager with plan modification methods

**How it integrates:**
- Hooks into existing failure path in `Agent._execute_action()`
- Uses existing `replan` action type to trigger replanning
- Leverages LLMService to analyze failure context and generate new plan
- Updates TodoList via TodoListManager with new/modified steps
- Persists modified plan via StateManager

**Success criteria:**
- Agent autonomously adapts plan after tool failures (instead of FAILED/SKIPPED)
- LLM generates contextual replan strategies based on error analysis
- At least 30% improvement in mission completion rate for recoverable failures
- Maximum 2 replan attempts per step to avoid infinite loops
- Clear logging of replan decisions and strategies

## Stories

1. **Story 3.1: Implement Replan Strategy Generation**
   - Design replan prompt template for LLM (analyze failure context → suggest strategy)
   - Implement three strategy types: parameter retry, tool swap, task decomposition
   - Add failure context extraction (error message, tool used, parameters, previous attempts)
   - Create `ReplanStrategy` dataclass with strategy_type, rationale, modifications
   - Add `generate_replan_strategy()` method to Agent using LLMService

2. **Story 3.2: Extend TodoListManager with Plan Modification**
   - Add `modify_step()` method to update TodoItem parameters/tool
   - Add `decompose_step()` method to split TodoItem into substeps
   - Add `replace_step()` method to swap step with alternative approach
   - Implement replan attempt tracking (`replan_count` field on TodoItem)
   - Add validation to prevent circular dependencies in modified plans

3. **Story 3.3: Integrate Replanning into Agent Execution Loop**
   - Implement `Agent._replan()` method using strategy generation
   - Hook replan trigger into failure path in `_execute_action()`
   - Add replan limit enforcement (max 2 replans per step)
   - Update MessageHistory to include replan context for LLM awareness
   - Add replan metrics logging (success rate, strategy distribution)
   - Create integration tests with deliberately failing tools

## Compatibility Requirements

- [x] Existing TodoList schema extended with `replan_count` field (default 0)
- [x] TaskStatus enum unchanged (reuse PENDING for retried steps)
- [x] Current retry logic (execute_safe) remains for simple failures
- [x] Replanning only triggers after all retries exhausted
- [x] Existing plan serialization/deserialization works with extended TodoItem

## Risk Mitigation

**Primary Risk:** Infinite replan loops or LLM generating invalid plan modifications

**Mitigation:**
- Hard limit of 2 replan attempts per TodoItem (tracked via `replan_count`)
- Schema validation for modified TodoList before persistence
- Dependency cycle detection in modified plans
- Fallback to FAILED status if replan limit exceeded
- Detailed logging of replan decisions for debugging

**Rollback Plan:**
- Revert `Agent._replan()` to mark step as SKIPPED (current behavior)
- Remove `replan_count` field from TodoItem (won't break existing plans)
- Disable replan action type in Agent execution loop
- No schema changes to StateManager or persistent data

## Definition of Done

- [x] All stories completed with acceptance criteria met
- [x] Agent autonomously replans after tool failures (3 retry attempts exhausted)
- [x] LLM generates valid replan strategies with clear rationale
- [x] Three strategy types implemented: retry, swap, decompose
- [x] Replan limit (max 2 per step) enforced to prevent loops
- [x] TodoListManager successfully modifies plans without corruption
- [x] Integration tests validate replan scenarios (parameter error, tool unavailable, dependency failure)
- [x] Replan metrics logged for observability
- [x] Existing functionality verified through regression testing
- [x] Documentation updated with replanning behavior and limitations

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing ReAct agent running Python 3.11 with LLM-based planning
- Integration points: 
  - Agent's `_replan()` method (currently TODO placeholder in `agent.py`)
  - TodoListManager for plan modification (`planning/todolist.py`)
  - LLMService for strategy generation
  - Failure path in `Agent._execute_action()` method
- Existing patterns to follow: 
  - LLM-based decision making with structured prompts
  - TodoList as JSON-serializable dataclass
  - Async execution with structured logging
- Critical compatibility requirements:
  - TodoItem schema extended backward-compatibly with `replan_count` field
  - Existing retry logic (execute_safe) remains primary failure handler
  - Replanning only triggers as last resort after retries
  - Plan modifications must pass dependency validation
- Each story must include verification that existing plan execution (no failures) remains intact
- Must test replan scenarios: library import error (suggest tool swap), parameter validation error (suggest retry with fix), complex task failure (suggest decomposition)

The epic should maintain system integrity while delivering autonomous failure recovery through intelligent replanning."

