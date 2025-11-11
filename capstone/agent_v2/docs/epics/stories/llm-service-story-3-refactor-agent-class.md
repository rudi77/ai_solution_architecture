# Story 3: Refactor Agent Class to Use LLMService

**Epic:** LLM Service Consolidation & Modernization  
**Story ID:** LLM-SERVICE-003  
**Status:** Ready for Development  
**Priority:** High  
**Estimated Effort:** 3-4 days  
**Dependencies:** Story 1 (LLMService created), Story 2 (Packages upgraded)

## Story Description

Replace direct `litellm.acompletion()` calls in `agent.py` with `LLMService` methods. Inject `LLMService` instance through constructor and update message compression and thought generation logic to use the centralized service.

## User Story

**As a** developer maintaining the Agent class  
**I want** the Agent to use LLMService instead of direct litellm calls  
**So that** all LLM interactions are centralized and model configuration is consistent

## Acceptance Criteria

### Functional Requirements

1. **Constructor Changes**
   - [x] `Agent.__init__()` accepts `llm_service: LLMService` parameter
   - [x] Store `llm_service` as instance attribute
   - [x] Remove direct `import litellm` from agent.py
   - [x] Update docstring to reflect new parameter

2. **MessageHistory Refactoring**
   - [x] `MessageHistory.compress_history_async()` uses `llm_service`
   - [x] Pass `llm_service` to `MessageHistory` constructor or method
   - [x] Remove direct `litellm.acompletion()` call (line ~106)
   - [x] Use `llm_service.complete()` instead
   - [x] Remove hardcoded model name ("gpt-4.1")

3. **Thought Generation Refactoring**
   - [x] `Agent.get_thought_agent_action_async()` uses `llm_service`
   - [x] Remove direct `litellm.acompletion()` call (line ~705)
   - [x] Use `llm_service.complete()` with model alias
   - [x] Remove hardcoded model name

4. **Model Configuration**
   - [x] All model references use aliases from config
   - [x] No hardcoded model names remain
   - [x] Use "main" alias for standard operations

5. **Backward Compatibility**
   - [x] Existing agent creation via factory still works
   - [x] All existing Agent tests pass (with mocking updates)
   - [x] Agent behavior unchanged from user perspective

### Non-Functional Requirements

- [x] Type annotations complete
- [x] Docstrings updated
- [x] No performance degradation
- [x] Logging maintained

## Technical Details

### Current Code (Before)

```python
# agent.py - CURRENT
import litellm

class MessageHistory:
    async def compress_history_async(self) -> None:
        """Summarize alte Messages mit LLM."""
        import litellm  # Direct import
        
        old_messages = self.messages[1:self.SUMMARY_THRESHOLD]
        
        summary_prompt = f"""Summarize this conversation history concisely:
{json.dumps(old_messages, indent=2)}
Provide a 2-3 paragraph summary of key decisions, results, and context."""
        
        try:
            response = await litellm.acompletion(  # Direct call
                model="gpt-4.1",  # Hardcoded
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0
            )
            # ... rest of method

class Agent:
    async def get_thought_agent_action_async(self, ...):
        # ... prepare messages ...
        
        response = await litellm.acompletion(  # Direct call
            model="gpt-4.1",  # Hardcoded
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7
        )
        # ... rest of method
```

### Refactored Code (After)

```python
# agent.py - REFACTORED
from capstone.agent_v2.services.llm_service import LLMService

class MessageHistory:
    def __init__(self, system_prompt: str, llm_service: LLMService):
        """
        Initialize message history.
        
        Args:
            system_prompt: The system prompt
            llm_service: LLM service for compression operations
        """
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.messages = [self.system_prompt]
        self.llm_service = llm_service  # Store service
    
    async def compress_history_async(self) -> None:
        """Summarize old messages using LLM service."""
        old_messages = self.messages[1:self.SUMMARY_THRESHOLD]
        
        summary_prompt = f"""Summarize this conversation history concisely:
{json.dumps(old_messages, indent=2)}
Provide a 2-3 paragraph summary of key decisions, results, and context."""
        
        try:
            # Use LLMService
            result = await self.llm_service.complete(
                messages=[{"role": "user", "content": summary_prompt}],
                model="main",  # Use alias
                temperature=0
            )
            
            if not result.get("success"):
                self.logger.error(
                    "compression_failed",
                    error=result.get("error")
                )
                return
            
            summary_text = result["content"]
            # ... rest of method unchanged


class Agent:
    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        tools: List[Tool],
        work_dir: str,
        todolist_manager: TodoListManager,
        state_manager: StateManager,
        llm_service: LLMService,  # NEW PARAMETER
        mission: Optional[str] = None
    ):
        """
        Initialize Agent.
        
        Args:
            name: Agent name
            description: Agent description
            system_prompt: System prompt
            tools: List of available tools
            work_dir: Working directory
            todolist_manager: Todo list manager
            state_manager: State manager
            llm_service: LLM service for completions
            mission: Optional mission
        """
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools
        self.work_dir = Path(work_dir)
        self.todolist_manager = todolist_manager
        self.state_manager = state_manager
        self.llm_service = llm_service  # Store service
        self.mission = mission
        self.logger = structlog.get_logger()
        
        # Update MessageHistory initialization
        self.message_history = MessageHistory(system_prompt, llm_service)
    
    async def get_thought_agent_action_async(
        self,
        current_step: TodoItem,
        available_tools_desc: str,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Get thought and action from LLM using ReAct pattern.
        
        Args:
            current_step: Current todo step
            available_tools_desc: Description of available tools
            messages: Conversation messages
            
        Returns:
            Dict with thought, action, and parameters
        """
        self.logger.info("llm_call_thought_start", step=current_step.position)
        
        # Use LLMService
        result = await self.llm_service.complete(
            messages=messages,
            model="main",  # Use alias
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        if not result.get("success"):
            self.logger.error(
                "thought_generation_failed",
                step=current_step.position,
                error=result.get("error")
            )
            raise RuntimeError(f"LLM completion failed: {result.get('error')}")
        
        # Parse response
        try:
            response_content = result["content"]
            thought_action = json.loads(response_content)
            
            self.logger.info(
                "llm_call_thought_complete",
                step=current_step.position,
                action=thought_action.get("action"),
                tokens=result.get("usage", {}).get("total_tokens", 0)
            )
            
            return thought_action
            
        except json.JSONDecodeError as e:
            self.logger.error(
                "thought_parse_failed",
                step=current_step.position,
                error=str(e),
                response=response_content[:200]
            )
            raise
```

## Files to Modify

### Primary File
1. **`capstone/agent_v2/agent.py`**
   - Add import: `from capstone.agent_v2.services.llm_service import LLMService`
   - Remove import: `import litellm` (global and in methods)
   - Update `MessageHistory.__init__()` to accept `llm_service`
   - Update `MessageHistory.compress_history_async()`
   - Update `Agent.__init__()` to accept `llm_service`
   - Update `Agent.get_thought_agent_action_async()`
   - Update all docstrings

### Test Files
2. **`capstone/agent_v2/tests/test_agent.py`** (if exists)
   - Update mocks to use `LLMService` instead of `litellm`
   - Update fixtures to provide `llm_service` instance

3. **`capstone/agent_v2/tests/integration/test_agent_integration.py`** (if exists)
   - Update integration tests to use `LLMService`
   - Verify end-to-end agent execution

## Testing Requirements

### Unit Tests

```python
# tests/test_agent_llm_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from capstone.agent_v2.agent import Agent, MessageHistory
from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock()
    return service


@pytest.fixture
def mock_todolist_manager():
    """Create mock TodoListManager."""
    return MagicMock()


@pytest.fixture
def mock_state_manager():
    """Create mock StateManager."""
    return MagicMock()


class TestMessageHistoryWithLLMService:
    """Test MessageHistory using LLMService."""
    
    @pytest.mark.asyncio
    async def test_compress_uses_llm_service(self, mock_llm_service):
        """Test that compress_history_async uses LLMService."""
        # Setup
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": "Summary of conversation",
            "usage": {"total_tokens": 100}
        }
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        # Add messages to trigger compression
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        # Compress
        await history.compress_history_async()
        
        # Verify LLMService was called
        mock_llm_service.complete.assert_called_once()
        
        # Verify model alias used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
    
    @pytest.mark.asyncio
    async def test_compress_handles_llm_failure(self, mock_llm_service):
        """Test compression handles LLM service failures gracefully."""
        # Setup failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "API error"
        }
        
        history = MessageHistory("System prompt", mock_llm_service)
        
        # Add messages
        for i in range(MessageHistory.SUMMARY_THRESHOLD + 5):
            history.add_message(f"Message {i}", "user")
        
        # Should not raise, just log error
        await history.compress_history_async()
        
        # Messages should remain unchanged
        assert len(history.messages) == MessageHistory.SUMMARY_THRESHOLD + 6


class TestAgentWithLLMService:
    """Test Agent using LLMService."""
    
    def test_agent_init_accepts_llm_service(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test Agent initialization with LLMService."""
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            tools=[],
            work_dir="./test_work",
            todolist_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        assert agent.llm_service is mock_llm_service
        assert agent.message_history.llm_service is mock_llm_service
    
    @pytest.mark.asyncio
    async def test_get_thought_uses_llm_service(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test thought generation uses LLMService."""
        # Setup
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"thought": "Test thought", "action": "test_action"}',
            "usage": {"total_tokens": 50}
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            tools=[],
            work_dir="./test_work",
            todolist_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        # Create mock TodoItem
        mock_step = MagicMock()
        mock_step.position = 1
        
        # Get thought
        result = await agent.get_thought_agent_action_async(
            current_step=mock_step,
            available_tools_desc="Tools: test",
            messages=[{"role": "user", "content": "Do something"}]
        )
        
        # Verify
        mock_llm_service.complete.assert_called_once()
        assert result["thought"] == "Test thought"
        assert result["action"] == "test_action"
        
        # Verify model alias used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
    
    @pytest.mark.asyncio
    async def test_get_thought_handles_llm_failure(
        self,
        mock_llm_service,
        mock_todolist_manager,
        mock_state_manager
    ):
        """Test thought generation handles LLM failures."""
        # Setup failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "API timeout"
        }
        
        agent = Agent(
            name="Test Agent",
            description="Test",
            system_prompt="You are helpful",
            tools=[],
            work_dir="./test_work",
            todolist_manager=mock_todolist_manager,
            state_manager=mock_state_manager,
            llm_service=mock_llm_service
        )
        
        mock_step = MagicMock()
        mock_step.position = 1
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="LLM completion failed"):
            await agent.get_thought_agent_action_async(
                current_step=mock_step,
                available_tools_desc="Tools: test",
                messages=[{"role": "user", "content": "Do something"}]
            )
```

### Integration Tests

```python
# tests/integration/test_agent_with_llm_service.py
import pytest
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.agent import Agent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_with_real_llm_service(tmp_path):
    """Integration test with real LLMService."""
    # Create LLMService with test config
    llm_service = LLMService(config_path="configs/llm_config.yaml")
    
    # Create Agent
    # ... (full agent setup)
    
    # Verify agent can perform basic operations
    # Note: May require API key for full test
```

## Validation Checklist

- [ ] `Agent.__init__()` accepts `llm_service` parameter
- [ ] `MessageHistory.__init__()` accepts `llm_service` parameter
- [ ] No direct `import litellm` in agent.py
- [ ] No direct `litellm.acompletion()` calls in agent.py
- [ ] No hardcoded model names ("gpt-4.1", etc.)
- [ ] All model references use aliases ("main")
- [ ] Type annotations complete
- [ ] Docstrings updated
- [ ] Unit tests pass
- [ ] Integration tests pass (if applicable)
- [ ] Code formatted with Black
- [ ] No linter errors (Ruff)
- [ ] Existing agent tests updated and passing

## Migration Notes

### For Developers

**Before this change:**
```python
# Agent directly imported and used litellm
import litellm
response = await litellm.acompletion(model="gpt-4.1", ...)
```

**After this change:**
```python
# Agent uses injected LLMService
result = await self.llm_service.complete(model="main", ...)
```

**Impact on agent creation:**
- Factory must now inject `llm_service` (handled in Story 6)
- Direct Agent instantiation requires `llm_service` parameter
- Tests must mock `llm_service` instead of `litellm`

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking existing agent creation | High | Update factory in Story 6, maintain backward compat |
| Test failures due to mocking changes | Medium | Update all test mocks systematically |
| Performance regression | Low | LLMService adds minimal overhead |
| Behavior changes | Low | Same underlying API, just wrapped |

## Definition of Done

- [x] Code changes implemented
- [x] `import litellm` removed from agent.py
- [x] All direct litellm calls replaced
- [x] No hardcoded model names
- [x] Type hints complete
- [x] Docstrings updated
- [x] Unit tests written and passing
- [x] Integration tests passing
- [x] Code formatted (Black)
- [x] Linting clean (Ruff)
- [x] Code review completed
- [x] Agent behavior verified unchanged

## Next Steps

After this story:
1. Story 4: Refactor LLMTool to use LLMService
2. Story 5: Refactor TodoListManager to use LLMService  
3. Story 6: Update AgentFactory to inject LLMService everywhere

---

**Story Created:** 2025-11-11  
**Last Updated:** 2025-11-11  
**Assigned To:** TBD  
**Reviewer:** TBD

