# Story: Native Tool Calling & Context Injection - Brownfield Enhancement

## Story Title

Native Tool Calling & Context Injection - Brownfield Enhancement

## User Story

As a **Developer**,
I want **to robustly handle LLM tool calls and inject the plan context dynamically**,
So that **the agent is resilient against parsing errors and "remembers" its progress.**

## Story Context

**Existing System Integration:**
- Integrates with: `agent.py` (Refactored `LeanAgent`), `llm_service.py` (possibly)
- Technology: `litellm` tool calling API
- Follows pattern: OpenAI Tool Calling Standard
- Touch points: `_execute_step` (or equivalent loop method)

## Acceptance Criteria

**Functional Requirements:**
1. Update LLM interaction to use `tool_choice="auto"` and pass `tools` schema natively.
2. Implement `_execute_tool_calls` handler:
   - Parses `message.tool_calls` from `litellm` response.
   - Parallel execution of independent tools (optional, sequential fine for start).
   - Captures outputs and appends `ToolMessage` (result) to history.
3. Implement Dynamic Context Injection:
   - Before each LLM call: `current_plan = self.planner.execute("read_plan")`.
   - Inject into System Prompt: `\n## CURRENT PLAN STATUS\n{current_plan}`.
4. Ensure `PlannerTool` execution updates the context for the *immediate next* step.

**Integration Requirements:**
5. Verify `WIKI_SYSTEM_PROMPT` and `KERNEL_PROMPT` work together with Native Tools.
6. Ensure "Thought" process is captured (LLMs often output content *before* tool calls - ensure this is saved to history).

**Quality Requirements:**
7. Error handling for failed tool executions (inject error back to LLM so it can retry).
8. No regex parsing for tool names/args.

## Technical Notes

- **Integration Approach:** Fine-tuning the loop created in Story 2.
- **Refactoring:** Ensure `tool.py` schemas are compatible with `litellm` expectation (usually JSON Schema).
- **Observation:** Native Tool Calling is much more stable than JSON mode for actions.

## Definition of Done

- [ ] Native Tool Calling implemented and verified.
- [ ] Context Injection (Plan Status) verified in logs/debug.
- [ ] Error handling for tool execution implemented.
- [ ] System Prompt assembly logic finalized.

## Risk and Compatibility Check

**Minimal Risk Assessment:**
- **Primary Risk:** LLM ignores the injected plan.
- **Mitigation:** Put the plan injection at the very end of the System Prompt ("Recency Bias").
- **Rollback:** Revert changes to `agent.py`.

**Compatibility Verification:**
- [x] No breaking changes to external API.
- [x] Improved robustness (non-functional requirement).

