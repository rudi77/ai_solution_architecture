# Story: Refactor Agent to LeanAgent - Brownfield Enhancement

## Story Title

Refactor Agent to LeanAgent - Brownfield Enhancement

## User Story

As a **Developer**,
I want **to replace the complex `agent.py` state machine with a simplified `LeanAgent` loop**,
So that **the codebase is easier to maintain and relies on native tool calling.**

## Story Context

**Existing System Integration:**
- Integrates with: `capstone/agent_v2/agent.py` (REPLACES existing logic)
- Technology: Python 3.x, `litellm`, `asyncio`
- Follows pattern: `ReAct` Loop (simplified)
- Touch points: `Agent` class, `create_agent` factory methods, CLI commands

## Acceptance Criteria

**Functional Requirements:**
1. Refactor `Agent` class in `agent.py`:
   - Remove `TodoListManager` usage.
   - Remove `QueryRouter`, `ReplanStrategy`, `Fast/Full Path` logic.
   - Remove `_generate_thought` and custom JSON parsing regex.
2. Implement single `execute(mission)` loop:
   - While `step_count < max_steps`:
     - Build System Prompt (Dynamic).
     - Call LLM with `tools` parameter.
     - If `tool_calls` present -> Execute -> Update History -> Loop.
     - If no `tool_calls` -> Return Content (Final Answer).
3. Initialize `PlannerTool` by default in `create_agent`.
4. Dynamic Prompt Assembly:
   - Combine `GENERAL_AUTONOMOUS_KERNEL_PROMPT` + `WIKI_SYSTEM_PROMPT` (if applicable).
   - Inject `planner.read_plan()` output if plan exists.

**Integration Requirements:**
5. CLI commands (`agent run mission`) must continue to work.
6. `StateManager` must now persist the simplified history + `PlannerTool` state instead of `TodoList` object.
7. Existing tools (Git, Web, etc.) must still work within the new loop.

**Quality Requirements:**
8. `agent.py` size reduced significantly (aim < 250 lines).
9. Explicit logging of tool execution and reasoning.

## Technical Notes

- **Integration Approach:** This is a "Big Cut". We are replacing the heart of the agent.
- **Backward Compatibility:** The external API (`agent.run()`) stays the same, but internal state representation changes. Old sessions might not be compatible (acceptable for this refactor).
- **Prompting:** Remove JSON formatting instructions from System Prompt that conflict with Native Tool Calling if necessary (though Kernel prompt might stay if we use `summary` field for final answer). *Correction from Epic:* We use Native Tools for actions, but might still want JSON for structured Final Answer? -> *Decision:* Lean Agent relies on standard string response for final answer unless structured output is strictly needed. Let's simplify to string response first.

## Definition of Done

- [ ] `Agent` class refactored to `LeanAgent` architecture.
- [ ] `TodoListManager` references removed.
- [ ] Single loop implementation verified.
- [ ] `PlannerTool` integrated into the loop.
- [ ] CLI smoke test passes.

## Risk and Compatibility Check

**Minimal Risk Assessment:**
- **Primary Risk:** Agent gets stuck in loops without the strict `TodoList` guidance.
- **Mitigation:** Injected Plan in System Prompt + Max Steps limit.
- **Rollback:** `git revert` of `agent.py`.

**Compatibility Verification:**
- [x] External API (`run`) remains compatible.
- [x] Internal State format changes (breaking for saved sessions - noted).
- [x] Tools remain compatible.

