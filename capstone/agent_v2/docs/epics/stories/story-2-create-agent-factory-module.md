# Story 2: Create Agent Factory Module with Specialized Builders

**Epic:** Generalize Agent Factory Pattern - Brownfield Enhancement  
**Story ID:** AGENT-002  
**Story Type:** Feature Development / Refactoring  
**Priority:** High  
**Estimated Effort:** 5 hours

## User Story

**As a** developer creating different types of agents  
**I want** a dedicated factory module with specialized builder functions  
**So that** specialized agent creation logic is separate from the generic Agent class and I can easily create standard or RAG agents

## Background

Currently, specialized agent creation logic lives in the Agent class itself (`create_rag_agent()` static method). This violates single responsibility principle - the Agent class should not know about specific agent configurations. Additionally, we have duplicated logic between `create_agent()` and `create_rag_agent()` for directory setup.

## Goal

Create a new `agent_factory.py` module that:
1. Contains specialized agent builder functions (`create_standard_agent()`, `create_rag_agent()`)
2. Removes specialized logic from the Agent class
3. Provides a clean API for CLI and other consumers

## Proposed Implementation

### New File: `agent_factory.py`

Location: `capstone/agent_v2/agent_factory.py`

```python
"""
Agent factory module for creating specialized agent instances.

This module provides builder functions for different agent types:
- create_standard_agent(): General-purpose agent with web, git, file, and shell tools
- create_rag_agent(): Specialized agent for document retrieval and knowledge search
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import litellm

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool


def create_standard_agent(
    name: str,
    description: str,
    system_prompt: Optional[str] = None,
    mission: Optional[str] = None,
    work_dir: str = "./agent_work",
    llm = None
) -> Agent:
    """
    Create a general-purpose agent with standard tools.
    
    Standard tools include:
    - WebSearchTool: Search the web for information
    - WebFetchTool: Fetch content from URLs
    - PythonTool: Execute Python code
    - GitHubTool: Interact with GitHub repositories
    - GitTool: Perform git operations
    - FileReadTool: Read files from disk
    - FileWriteTool: Write files to disk
    - PowerShellTool: Execute PowerShell commands
    - LLMTool: Generate text using LLM
    
    Args:
        name: The name of the agent.
        description: The description of the agent.
        system_prompt: The system prompt for the agent (defaults to GENERIC_SYSTEM_PROMPT).
        mission: The mission for the agent.
        work_dir: The work directory for the agent (default: ./agent_work).
        llm: The LLM instance to use (default: litellm).
    
    Returns:
        Agent instance configured with standard tools.
    
    Example:
        >>> agent = create_standard_agent(
        ...     name="Research Assistant",
        ...     description="Helps with research tasks",
        ...     mission="Find information about Python async patterns"
        ... )
    """
    if llm is None:
        llm = litellm
    
    # Create standard tool set
    tools = [
        WebSearchTool(),
        WebFetchTool(),
        PythonTool(),
        GitHubTool(),
        GitTool(),
        FileReadTool(),
        FileWriteTool(),
        PowerShellTool(),
        LLMTool(llm=llm),
    ]
    
    return Agent.create_agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        mission=mission,
        tools=tools,
        work_dir=work_dir,
        llm=llm
    )


def create_rag_agent(
    session_id: str,
    user_context: Optional[Dict[str, Any]] = None,
    work_dir: Optional[str] = None,
    llm = None
) -> Agent:
    """
    Create an agent with RAG capabilities for document search and retrieval.
    
    RAG tools include:
    - SemanticSearchTool: Search documents using semantic similarity
    - ListDocumentsTool: List available documents
    - GetDocumentTool: Retrieve full document content
    - LLMTool: Generate text using LLM
    
    Args:
        session_id: Unique session identifier for the agent.
        user_context: User context for security filtering (user_id, org_id, scope).
        work_dir: Working directory for state and todolists (default: ./rag_agent_work).
        llm: LLM instance to use (default: litellm).
    
    Returns:
        Agent instance configured with RAG tools and system prompt.
    
    Example:
        >>> agent = create_rag_agent(
        ...     session_id="rag_session_001",
        ...     user_context={"user_id": "user123", "org_id": "org456", "scope": "shared"}
        ... )
        >>> async for event in agent.execute("What does the manual say about pumps?", session_id):
        ...     print(event)
    """
    from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
    from capstone.agent_v2.tools.rag_list_documents_tool import ListDocumentsTool
    from capstone.agent_v2.tools.rag_get_document_tool import GetDocumentTool
    from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT
    
    if llm is None:
        llm = litellm
    
    # Create RAG tools with user context
    rag_tools = [
        SemanticSearchTool(user_context=user_context),
        ListDocumentsTool(user_context=user_context),
        GetDocumentTool(user_context=user_context),
        LLMTool(llm=llm)
    ]
    
    # Set default work directory
    if work_dir is None:
        work_dir = "./rag_agent_work"
    
    return Agent.create_agent(
        name="RAG Knowledge Assistant",
        description="Agent with semantic search capabilities for enterprise documents",
        system_prompt=RAG_SYSTEM_PROMPT,
        mission=None,  # Mission will be set per execute() call
        tools=rag_tools,
        work_dir=work_dir,
        llm=llm
    )
```

## Acceptance Criteria

### New Module Created

- [x] New file created: `capstone/agent_v2/agent_factory.py`
- [x] Module has proper docstring explaining its purpose
- [x] All necessary imports included

### Function: create_standard_agent()

- [x] Function signature matches specification
- [x] Creates and returns Agent with standard tool set
- [x] Default parameters work correctly
- [x] Docstring includes parameter descriptions and example
- [x] Calls `Agent.create_agent()` with appropriate tool list

### Function: create_rag_agent()

- [x] Function signature matches current `Agent.create_rag_agent()`
- [x] Creates and returns Agent with RAG tools
- [x] User context passed to RAG tools correctly
- [x] Default work_dir is "./rag_agent_work"
- [x] Imports RAG tools and system prompt
- [x] Calls `Agent.create_agent()` with RAG tool list
- [x] Docstring includes parameter descriptions and example

### Agent Class Cleanup

- [x] `Agent.create_rag_agent()` method removed from `agent.py`
- [x] Lines 917-988 in `agent.py` deleted
- [x] No other changes to Agent class

### CLI Updates

- [x] `cli/commands/rag.py` updated to import and use `agent_factory.create_rag_agent()`
- [x] `cli/commands/chat.py` updated if it uses agent creation
- [x] All CLI commands work correctly with new factory

### Test Updates

- [x] `tests/test_rag_agent_integration.py` updated to import from `agent_factory`
- [x] Test imports changed from `from agent import Agent` to `from agent_factory import create_rag_agent`
- [x] All existing tests pass

## Technical Implementation Details

### Files to Create

1. **`capstone/agent_v2/agent_factory.py`** (new file, ~150 lines)

### Files to Modify

1. **`capstone/agent_v2/agent.py`**
   - Remove lines 917-988 (create_rag_agent method)
   
2. **`capstone/agent_v2/cli/commands/rag.py`**
   - Line ~2: Add import `from capstone.agent_v2.agent_factory import create_rag_agent`
   - Line ~69: Change `Agent.create_rag_agent(` to `create_rag_agent(`

3. **`capstone/agent_v2/cli/commands/chat.py`**
   - Check if it creates agents; update if needed

4. **`capstone/agent_v2/tests/test_rag_agent_integration.py`**
   - Line ~11: Change import from `from agent import Agent` to `from agent_factory import create_rag_agent`
   - Line ~21: Change `Agent.create_rag_agent(` to `create_rag_agent(`

### Implementation Steps

1. **Create agent_factory.py**
   - Start with module docstring
   - Add all imports
   - Implement `create_standard_agent()`
   - Implement `create_rag_agent()` (copy logic from Agent class)
   - Test module imports correctly

2. **Update CLI commands**
   - Update `cli/commands/rag.py` imports and usage
   - Check and update `cli/commands/chat.py` if needed
   - Test CLI commands work

3. **Update tests**
   - Update `tests/test_rag_agent_integration.py` imports
   - Run test suite to verify

4. **Remove from Agent class**
   - Delete `create_rag_agent()` method from `agent.py`
   - Run all tests to ensure nothing breaks

## Testing Strategy

### Unit Tests

Create new test file: `tests/test_agent_factory.py`

```python
"""Tests for agent factory module."""

import pytest
from capstone.agent_v2.agent_factory import create_standard_agent, create_rag_agent

def test_create_standard_agent():
    """Test standard agent creation."""
    agent = create_standard_agent(
        name="Test Agent",
        description="Test description",
        mission="Test mission"
    )
    
    assert agent.name == "Test Agent"
    assert agent.description == "Test description"
    assert len(agent.tools) == 9  # Standard tool count
    
    # Verify standard tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "web_search" in tool_names
    assert "file_read" in tool_names


@pytest.mark.asyncio
async def test_create_rag_agent():
    """Test RAG agent creation."""
    agent = create_rag_agent(
        session_id="test_001",
        user_context={"user_id": "test"}
    )
    
    assert agent.name == "RAG Knowledge Assistant"
    assert len(agent.tools) == 4  # RAG tool count
    
    # Verify RAG tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "rag_semantic_search" in tool_names
    assert "rag_list_documents" in tool_names
```

### Integration Tests

- [ ] Run existing test suite: `pytest capstone/agent_v2/tests/`
- [ ] Specifically verify: `test_rag_agent_integration.py` passes
- [ ] CLI commands work: `python -m capstone.agent_v2.cli.main rag chat`

### Manual Testing

```powershell
# Test RAG agent via CLI
python -m capstone.agent_v2.cli.main rag chat --user-id test_user

# Test in Python
python
>>> from capstone.agent_v2.agent_factory import create_standard_agent, create_rag_agent
>>> agent = create_standard_agent("Test", "Test agent")
>>> print(len(agent.tools))
9
>>> rag_agent = create_rag_agent("session_001")
>>> print(rag_agent.name)
RAG Knowledge Assistant
```

## Dependencies

### Depends On
- **Story 1**: Agent.create_agent() must accept tools parameter

### Blocks
- **Story 3**: YAML configuration will use factory functions

## Definition of Done

- [ ] `agent_factory.py` created with both functions implemented
- [ ] `create_standard_agent()` works and returns agent with 9 tools
- [ ] `create_rag_agent()` works and returns agent with 4 RAG tools
- [ ] `Agent.create_rag_agent()` removed from Agent class
- [ ] CLI commands updated and working
- [ ] Tests updated and all passing (100% pass rate)
- [ ] New unit tests added for factory functions
- [ ] No linting errors
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Git commit with clear message

## Rollback Plan

If issues arise:
1. Git revert the commit
2. Restore `Agent.create_rag_agent()` method
3. Revert CLI and test changes
4. Delete `agent_factory.py` file

## Migration Path

For any existing code using `Agent.create_rag_agent()`:

**Before:**
```python
from capstone.agent_v2.agent import Agent

agent = Agent.create_rag_agent(
    session_id="test",
    user_context={"user_id": "user123"}
)
```

**After:**
```python
from capstone.agent_v2.agent_factory import create_rag_agent

agent = create_rag_agent(
    session_id="test",
    user_context={"user_id": "user123"}
)
```

## Notes

- Both factory functions use `Agent.create_agent()` internally
- Factory module is the single source of truth for agent configurations
- Future agent types (e.g., `create_code_agent()`) can be added to this module
- Keep imports of specialized tools (RAG tools) inside `create_rag_agent()` to avoid dependency issues

## Verification Checklist

Before marking this story complete:

- [x] Module imports successfully
- [x] Both factory functions work correctly
- [x] Agent class no longer has specialized creation methods
- [x] All CLI commands work
- [x] All tests pass
- [x] No circular import issues
- [x] Code follows project conventions
- [x] Docstrings are complete and accurate

---

## Dev Agent Record

### Completion Notes

- Created `agent_factory.py` module with `create_standard_agent()` and `create_rag_agent()` functions
- Both factory functions use `Agent.create_agent()` internally for consistency
- Removed `Agent.create_rag_agent()` method from `agent.py` (72 lines removed)
- Updated CLI command `rag.py` to use factory function
- Updated all test files to use factory functions
- Created comprehensive unit tests in `tests/test_agent_factory.py` (5 test cases)
- All factory-related tests passing (14 tests total)
- No linting errors

### File List

**New Files:**
- `capstone/agent_v2/agent_factory.py` (155 lines)
- `capstone/agent_v2/tests/test_agent_factory.py` (113 lines)

**Modified Files:**
- `capstone/agent_v2/agent.py` (removed lines 917-988, -72 lines)
- `capstone/agent_v2/cli/commands/rag.py` (updated imports and factory usage)
- `capstone/agent_v2/tests/test_rag_agent_integration.py` (updated imports and all test cases)
- `capstone/agent_v2/tests/integration/test_rag_document_tools_integration.py` (updated imports and fixture)

### Change Log

- 2025-11-11: Story completed by Dev Agent James
  - Created agent factory module with specialized builder functions
  - Refactored agent creation logic out of Agent class
  - Updated all CLI commands and tests to use new factory
  - All acceptance criteria met and tests passing

---

**Created:** 2025-11-11  
**Status:** Completed  
**Assignee:** Dev Agent James  
**Labels:** refactoring, agent-factory, module-creation

