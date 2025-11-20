# Epic 2: Human-in-the-Loop Approval Gate - Brownfield Enhancement

## Epic Goal

Implement a security approval system for sensitive tool operations that requires explicit user consent before executing high-risk commands, making the agent Enterprise-ready and trustworthy for production environments.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- ReAct agent with autonomous tool execution (PowerShellTool, PythonTool, FileWriteTool, GitTool, etc.)
- Basic blacklist validation in tools (e.g., `rm -rf` protection in PowerShellTool)
- Tool base class with `execute()` and `execute_safe()` methods
- Agent orchestration with action types: tool_call, ask_user, complete, replan

**Technology stack:**
- Python 3.11 with asyncio
- Base Tool class (`capstone/agent_v2/tool.py`)
- Agent class with action execution (`capstone/agent_v2/agent.py`)
- StateManager for session persistence

**Integration points:**
- Tool execution flow in `Agent._execute_action()` method
- `ask_user` action type already exists for clarification questions
- Tool base class for adding new properties/metadata

### Enhancement Details

**What's being added/changed:**
- Add `requires_approval: bool = False` flag to Tool base class
- Implement approval policy checking in Agent before executing sensitive tools
- Extend ASK_USER mechanism to handle approval requests with clear command preview
- Add configurable approval policies (always_approve, always_deny, prompt_user)
- Mark high-risk tools (WriteFile, PowerShell, GitPush) as requiring approval

**How it integrates:**
- Extends existing Tool base class with new metadata property
- Hooks into Agent's `_execute_action()` method before tool execution
- Reuses existing `ask_user` action flow for approval prompts
- Stores approval responses in StateManager for session continuity

**Success criteria:**
- Sensitive tools pause execution and request user approval
- Clear preview of command/operation shown to user before approval
- User can approve (y), deny (n), or skip approval for session
- No regression in non-sensitive tool execution speed
- Audit log of approved/denied operations

## Stories

1. **Story 2.1: Extend Tool Base Class with Approval Metadata**
   - Add `requires_approval` property to Tool base class
   - Add `approval_policy` enum (PROMPT, AUTO_APPROVE, AUTO_DENY)
   - Add `get_approval_preview()` method to format command preview
   - Update PowerShellTool, FileWriteTool, GitTool to set `requires_approval=True`

2. **Story 2.2: Implement Approval Gate in Agent Execution Flow**
   - Add approval check in `Agent._execute_action()` before tool execution
   - Implement approval prompt generation with command preview
   - Extend `ask_user` flow to handle approval requests
   - Store approval decisions in StateManager for session context
   - Add audit logging for all approval decisions

3. **Story 2.3: Add Configurable Approval Policies and Testing**
   - Add approval policy configuration to Agent initialization
   - Implement session-based "trust mode" (skip approvals for session)
   - Create integration tests for approval workflows
   - Add CLI flag `--auto-approve` for trusted automation scenarios
   - Update documentation with security best practices

## Compatibility Requirements

- [x] Existing tool execution API remains unchanged for tools with `requires_approval=False`
- [x] Non-sensitive tools execute without approval overhead
- [x] Existing `ask_user` mechanism works for clarification questions
- [x] StateManager schema extended backward-compatibly with `approval_history` field
- [x] CLI commands work unchanged unless `--auto-approve` flag is used

## Risk Mitigation

**Primary Risk:** Over-prompting annoys users in safe scenarios; under-prompting allows dangerous operations

**Mitigation:**
- Granular control via tool-level `requires_approval` flag
- Session-based trust mode reduces repeated prompts
- Clear command preview helps users make informed decisions
- `--auto-approve` flag for trusted automation pipelines

**Rollback Plan:**
- Default `requires_approval=False` means zero impact if feature disabled
- Remove approval check from `_execute_action()` method
- No database/schema changes required for rollback

## Definition of Done

- [x] All stories completed with acceptance criteria met
- [x] High-risk tools (PowerShell, FileWrite, Git push) require approval by default
- [x] Approval prompts show clear command preview
- [x] User can approve/deny/trust for session
- [x] Audit log records all approval decisions
- [x] Integration tests validate approval workflows
- [x] Existing functionality verified through regression testing
- [x] No performance degradation for non-sensitive tools
- [x] Documentation updated with security guidelines

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing ReAct agent running Python 3.11 with asyncio
- Integration points: Tool base class (`tool.py`), Agent execution flow (`agent.py:_execute_action`), existing `ask_user` action type, StateManager for persistence
- Existing patterns to follow: Tool metadata properties, async execute methods, action-based control flow
- Critical compatibility requirements: 
  - Zero performance impact for non-sensitive tools
  - Backward-compatible StateManager schema extension
  - Existing tool execution API unchanged
  - CLI remains functional with optional `--auto-approve` flag
- Each story must include verification that existing tool execution (non-sensitive) remains intact
- Must test approval workflows with PowerShellTool, FileWriteTool, and GitTool

The epic should maintain system integrity while delivering security-first tool execution control."

