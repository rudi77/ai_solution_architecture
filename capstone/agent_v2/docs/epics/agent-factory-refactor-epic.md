# Epic: Generalize Agent Factory Pattern - Brownfield Enhancement

## Epic Goal

Refactor agent creation to use a unified, configurable factory pattern that supports YAML-based configuration and moves specialized agent logic out of the generic Agent class, improving maintainability and extensibility.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- Agent class (`agent.py`) contains two static factory methods:
  - `create_agent()`: Creates standard agent with web, git, file, and shell tools
  - `create_rag_agent()`: Creates specialized RAG agent with semantic search tools
- Both methods duplicate directory setup logic (work_dir, todolists, states)
- Specialized agent configuration is hardcoded in the generic Agent class

**Technology stack:**
- Python 3.x with dataclasses
- Async/await patterns (asyncio)
- litellm for LLM interactions
- structlog for logging
- Various tool implementations (FileReadTool, GitTool, SemanticSearchTool, etc.)

**Integration points:**
- CLI commands (`cli/commands/chat.py`, `cli/commands/rag.py`) call factory methods
- Test suite (`tests/test_rag_agent_integration.py`) validates agent creation
- Tool registration happens during agent instantiation

### Enhancement Details

**What's being added/changed:**

1. **Unified Factory Method:**
   - Replace `create_agent()` and `create_rag_agent()` with single `create_agent()` method
   - Accept flexible parameters: name, description, system_prompt, mission, tools, work_dir, llm
   - Tools parameter accepts list of Tool instances (not hardcoded)

2. **Specialized Agent Factories (New Module):**
   - Create `agent_factory.py` module for specialized agent builders
   - Move RAG agent creation logic to `create_rag_agent()` function in factory module
   - Move standard agent creation to `create_standard_agent()` function in factory module

3. **YAML Configuration Support:**
   - Create `AgentConfig` dataclass to hold agent configuration
   - Implement `load_agent_config_from_yaml(path)` function
   - YAML schema supports: name, description, system_prompt_file, tools (list of tool specs), work_dir
   - Implement `create_agent_from_config(config)` function

**How it integrates:**
- Backward compatibility: Existing CLI and tests updated to use factory module functions
- Agent class remains unchanged except for simplified factory method
- YAML configs stored in `capstone/agent_v2/configs/` directory
- Tool specification in YAML maps to Tool class instantiation

**Success criteria:**
- All existing tests pass without modification to test logic
- CLI commands work with new factory pattern
- Can create RAG agent from YAML file
- Code duplication eliminated (directory setup logic in one place)
- Agent class has no specialized agent knowledge

## Stories

### Story 1: Refactor Agent.create_agent() to Accept Tool List

**Description:** Simplify the `Agent.create_agent()` static method to accept a list of Tool instances instead of hardcoding standard tools. Extract common setup logic (directory creation, managers) into the unified method.

**Acceptance Criteria:**
- `create_agent()` signature: `create_agent(name, description, system_prompt, mission, tools: List[Tool], work_dir, llm)`
- Method handles work_dir, todolist_dir, state_dir creation
- Method creates TodoListManager and StateManager
- Returns Agent instance with provided tools
- Existing `create_rag_agent()` still works

**Technical Details:**
- Update signature to accept `tools: List[Tool]` parameter
- Remove hardcoded tool instantiation
- Keep directory setup and manager creation logic
- Ensure backward compatibility with existing calls

### Story 2: Create Agent Factory Module with Specialized Builders

**Description:** Create new `agent_factory.py` module and move specialized agent creation logic out of Agent class. Implement `create_standard_agent()` and `create_rag_agent()` functions. Update CLI and tests to use factory functions.

**Acceptance Criteria:**
- New file: `capstone/agent_v2/agent_factory.py`
- Function `create_standard_agent(name, description, system_prompt, mission, work_dir, llm)` returns Agent with web/git/file tools
- Function `create_rag_agent(session_id, user_context, work_dir, llm)` returns RAG agent
- Remove `Agent.create_rag_agent()` from Agent class
- Update `cli/commands/rag.py` to use `agent_factory.create_rag_agent()`
- Update `cli/commands/chat.py` to use factory if applicable
- All tests pass

**Technical Details:**
- Import statements in factory: all Tool classes, Agent class
- `create_standard_agent()` instantiates: WebSearchTool, WebFetchTool, PythonTool, GitHubTool, GitTool, FileReadTool, FileWriteTool, PowerShellTool, LLMTool
- `create_rag_agent()` instantiates: SemanticSearchTool, ListDocumentsTool, GetDocumentTool, LLMTool
- Both functions call `Agent.create_agent()` with appropriate tool list
- Update import statements in CLI and tests

### Story 3: Implement YAML-Based Agent Configuration

**Description:** Add support for defining agents via YAML configuration files. Create AgentConfig dataclass, YAML loader, and factory function to create agents from config.

**Acceptance Criteria:**
- New `AgentConfig` dataclass in `agent_factory.py`
- Function `load_agent_config_from_yaml(path: str) -> AgentConfig`
- Function `create_agent_from_config(config: AgentConfig) -> Agent`
- YAML schema supports: name, description, system_prompt (file path or inline), tools (list with type and params), work_dir
- Example YAML file: `configs/rag_agent.yaml`
- Documentation with YAML schema example
- Can instantiate RAG agent from YAML file

**Technical Details:**
- `AgentConfig` fields: name, description, system_prompt, system_prompt_file, tools, work_dir, llm_config
- Tool spec format: `{type: "SemanticSearchTool", params: {user_context: {...}}}`
- Tool type mapping to Tool classes
- Load system prompt from file if `system_prompt_file` specified
- Handle optional parameters with sensible defaults

## Compatibility Requirements

- ✅ **Existing APIs:** CLI commands updated but behavior unchanged
- ✅ **Database schema:** N/A (no database)
- ✅ **UI changes:** N/A (CLI-only)
- ✅ **Performance impact:** Minimal (same object instantiation, different path)
- ✅ **Backward compatibility:** Agent class constructor unchanged, factory methods enhanced

## Risk Mitigation

**Primary Risk:** Breaking existing tests or CLI functionality during refactoring

**Mitigation:**
- Implement changes incrementally (3 stories)
- Run full test suite after each story
- Keep existing `create_rag_agent()` until Story 2 complete
- Update one CLI command at a time

**Rollback Plan:**
- Git revert to previous commit if tests fail
- Each story is independently committable
- No database migrations or external dependencies

## Definition of Done

- ✅ All existing tests pass (`test_rag_agent_integration.py`, etc.)
- ✅ No specialized agent logic remains in `agent.py`
- ✅ CLI commands (`rag chat`, `chat`) work correctly
- ✅ Can create RAG agent from YAML configuration file
- ✅ Code duplication eliminated (directory setup in one place)
- ✅ Example YAML configuration file created
- ✅ No regression in agent execution or tool registration

## Validation Checklist

**Scope Validation:**
- ✅ Epic completable in 3 stories
- ✅ No architectural changes (refactoring only)
- ✅ Follows existing patterns (factory pattern, dataclasses)
- ✅ Integration complexity manageable (CLI updates only)

**Risk Assessment:**
- ✅ Risk to existing system: LOW (pure refactoring, tests validate)
- ✅ Rollback plan feasible (git revert)
- ✅ Testing approach: Run existing test suite
- ✅ Team has sufficient knowledge (Python, YAML, factory pattern)

**Completeness Check:**
- ✅ Epic goal clear and achievable
- ✅ Stories properly scoped and sequenced
- ✅ Success criteria measurable (tests pass, YAML works)
- ✅ Dependencies identified (Story 2 depends on Story 1)

## Story Manager Handoff

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing Python agent system using async/await patterns and litellm
- Integration points:
  - CLI commands in `cli/commands/rag.py` and `cli/commands/chat.py`
  - Test suite in `tests/test_rag_agent_integration.py`
  - Agent class constructor must remain unchanged
- Existing patterns to follow:
  - Dataclasses for configuration
  - Static factory methods
  - Path objects for directory handling
- Critical compatibility requirements:
  - All existing tests must pass
  - CLI behavior unchanged from user perspective
  - Agent runtime behavior identical
- Each story must include verification that:
  - Existing test suite passes
  - CLI commands work correctly
  - No regression in agent execution

The epic should improve code maintainability and extensibility while maintaining system integrity and delivering a flexible, YAML-configurable agent factory pattern."

## Example YAML Configuration

Here's a proposed example of what the YAML configuration would look like:

```yaml
# configs/rag_agent.yaml
name: "RAG Knowledge Assistant"
description: "Agent with semantic search capabilities for enterprise documents"
system_prompt_file: "prompts/rag_system_prompt.py"
work_dir: "./rag_agent_work"

tools:
  - type: SemanticSearchTool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: ListDocumentsTool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: GetDocumentTool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: LLMTool
    params: {}

llm_config:
  provider: "litellm"
  model: "gpt-4o-mini"
```

## Project Analysis Checklist

### Existing Project Context
- ✅ Project purpose and current functionality understood
- ✅ Existing technology stack identified
- ✅ Current architecture patterns noted
- ✅ Integration points with existing system identified

### Enhancement Scope
- ✅ Enhancement clearly defined and scoped
- ✅ Impact on existing functionality assessed
- ✅ Required integration points identified
- ✅ Success criteria established

---

**Epic Created:** 2025-11-11  
**Epic Status:** Ready for Story Development  
**Estimated Stories:** 3  
**Complexity:** Medium (Refactoring with YAML config)  
**Risk Level:** Low

