# Story 5: Refactor TodoListManager to Use LLMService

**Epic:** LLM Service Consolidation & Modernization  
**Story ID:** LLM-SERVICE-005  
**Status:** Ready for Review  
**Priority:** High  
**Estimated Effort:** 2-3 days  
**Dependencies:** Story 1 (LLMService created)

## Story Description

Update `TodoListManager` to use `LLMService` for clarification question generation and todo list creation. Remove direct litellm calls, eliminate hardcoded model names, and use model aliases for different task types.

## User Story

**As a** developer maintaining the planning system  
**I want** TodoListManager to use LLMService for LLM operations  
**So that** planning operations benefit from centralized configuration and can use appropriate models for different tasks

## Acceptance Criteria

### Functional Requirements

1. **Constructor Changes**
   - [x] `TodoListManager.__init__()` accepts `llm_service: LLMService` parameter
   - [x] Store `llm_service` as instance attribute
   - [x] Remove direct `import litellm` from todolist.py
   - [x] Update docstring

2. **Clarification Questions Refactoring**
   - [x] `create_questions_async()` uses `llm_service.complete()`
   - [x] Remove direct `litellm.acompletion()` call (line ~247)
   - [x] Remove hardcoded model name ("gpt-4.1")
   - [x] Use model alias "main" for standard operations

3. **Todo List Generation Refactoring**
   - [x] `generate_todolist_async()` uses `llm_service.complete()`
   - [x] Remove direct `litellm.acompletion()` call (line ~354)
   - [x] Remove hardcoded model name ("gpt-4.1-mini")
   - [x] Use model alias "fast" for quick tasks

4. **Model Strategy**
   - [x] Use "main" alias for complex reasoning (clarification questions)
   - [x] Use "fast" alias for structured tasks (todo list generation)
   - [x] Allow model override via parameters if needed

5. **Error Handling**
   - [x] Use service's error responses
   - [x] Maintain existing error handling patterns
   - [x] Log service errors appropriately

### Non-Functional Requirements

- [x] Type annotations complete
- [x] Docstrings updated  
- [x] All todolist tests pass
- [x] No performance degradation

## Technical Details

### Current Code (Before)

```python
# planning/todolist.py - CURRENT
import litellm


class TodoListManager:
    def __init__(self, todolist_dir: str):
        """Initialize TodoListManager."""
        self.todolist_dir = Path(todolist_dir)
        self.todolist_dir.mkdir(parents=True, exist_ok=True)
        self.logger = structlog.get_logger()
    
    async def create_questions_async(self, mission: str, tools_desc: str) -> List[str]:
        """
        Generate clarification questions for a mission.
        
        Returns:
            A list of clarification questions.
        """
        user_prompt, system_prompt = self.create_clarification_questions_prompts(mission, tools_desc)
        response = await litellm.acompletion(  # Direct call
            model="gpt-4.1",  # Hardcoded
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        # ... rest of method
    
    async def generate_todolist_async(
        self, 
        mission: str, 
        tools_desc: str, 
        answers: Dict[str, str]
    ) -> TodoList:
        """
        Generate a TodoList from mission and answers.
        
        Returns:
            Generated TodoList
        """
        user_prompt, system_prompt = self.create_final_todolist_prompts(mission, tools_desc, answers)
        
        response = await litellm.acompletion(  # Direct call
            model="gpt-4.1-mini",  # Hardcoded - fast model for structured task
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        # ... rest of method
```

### Refactored Code (After)

```python
# planning/todolist.py - REFACTORED
from capstone.agent_v2.services.llm_service import LLMService


class TodoListManager:
    """
    Manager for creating and managing Todo Lists using LLMService.
    
    Uses different model strategies:
    - "main" model for complex reasoning (clarification questions)
    - "fast" model for structured generation (todo lists)
    """
    
    def __init__(self, todolist_dir: str, llm_service: LLMService):
        """
        Initialize TodoListManager with LLMService.
        
        Args:
            todolist_dir: Directory for storing todolists
            llm_service: LLM service for generation operations
        """
        self.todolist_dir = Path(todolist_dir)
        self.todolist_dir.mkdir(parents=True, exist_ok=True)
        self.llm_service = llm_service
        self.logger = structlog.get_logger()
    
    async def create_questions_async(
        self, 
        mission: str, 
        tools_desc: str,
        model: str = "main"  # Allow override
    ) -> List[str]:
        """
        Generate clarification questions for a mission using LLM.
        
        Uses "main" model by default for complex reasoning.
        
        Args:
            mission: The mission description
            tools_desc: Description of available tools
            model: Model alias to use (default: "main")
            
        Returns:
            A list of clarification questions.
            
        Raises:
            RuntimeError: If LLM generation fails
        """
        user_prompt, system_prompt = self.create_clarification_questions_prompts(
            mission, 
            tools_desc
        )
        
        self.logger.info(
            "creating_clarification_questions",
            mission_length=len(mission),
            model=model
        )
        
        # Use LLMService
        result = await self.llm_service.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,  # Use alias
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        if not result.get("success"):
            self.logger.error(
                "clarification_questions_failed",
                error=result.get("error")
            )
            raise RuntimeError(f"Failed to generate questions: {result.get('error')}")
        
        # Parse JSON response
        try:
            response_content = result["content"]
            data = json.loads(response_content)
            questions = data.get("questions", [])
            
            self.logger.info(
                "clarification_questions_generated",
                question_count=len(questions),
                tokens=result.get("usage", {}).get("total_tokens", 0)
            )
            
            return questions
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(
                "clarification_questions_parse_failed",
                error=str(e),
                response=response_content[:200]
            )
            raise RuntimeError(f"Failed to parse questions: {e}")
    
    async def generate_todolist_async(
        self, 
        mission: str, 
        tools_desc: str, 
        answers: Dict[str, str],
        model: str = "fast"  # Fast model for structured task
    ) -> TodoList:
        """
        Generate a TodoList from mission and answers using LLM.
        
        Uses "fast" model by default for efficient structured generation.
        
        Args:
            mission: The mission description
            tools_desc: Description of available tools
            answers: Dict of question-answer pairs
            model: Model alias to use (default: "fast")
            
        Returns:
            Generated TodoList
            
        Raises:
            RuntimeError: If LLM generation fails
        """
        user_prompt, system_prompt = self.create_final_todolist_prompts(
            mission, 
            tools_desc, 
            answers
        )
        
        self.logger.info(
            "generating_todolist",
            mission_length=len(mission),
            answer_count=len(answers),
            model=model
        )
        
        # Use LLMService with fast model for structured task
        result = await self.llm_service.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,  # Use "fast" alias
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        if not result.get("success"):
            self.logger.error(
                "todolist_generation_failed",
                error=result.get("error")
            )
            raise RuntimeError(f"Failed to generate todolist: {result.get('error')}")
        
        # Parse JSON response into TodoList
        try:
            response_content = result["content"]
            todolist_data = json.loads(response_content)
            
            # Create TodoList from parsed data
            todolist = self._parse_todolist_data(todolist_data, mission)
            
            self.logger.info(
                "todolist_generated",
                step_count=len(todolist.steps),
                tokens=result.get("usage", {}).get("total_tokens", 0)
            )
            
            return todolist
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(
                "todolist_parse_failed",
                error=str(e),
                response=response_content[:200]
            )
            raise RuntimeError(f"Failed to parse todolist: {e}")
    
    def _parse_todolist_data(self, data: Dict[str, Any], mission: str) -> TodoList:
        """
        Parse todolist data from LLM response into TodoList object.
        
        Args:
            data: Parsed JSON data from LLM
            mission: Original mission
            
        Returns:
            TodoList instance
        """
        steps = []
        for step_data in data.get("steps", []):
            step = TodoItem(
                position=step_data["position"],
                description=step_data["description"],
                depends_on=step_data.get("depends_on", []),
                status=TaskStatus.PENDING,
                tool_call=step_data.get("tool_call"),
                rationale=step_data.get("rationale", "")
            )
            steps.append(step)
        
        return TodoList(
            mission=mission,
            steps=steps,
            open_questions=data.get("open_questions", [])
        )
```

## Files to Modify

1. **`capstone/agent_v2/planning/todolist.py`**
   - Add import: `from capstone.agent_v2.services.llm_service import LLMService`
   - Remove import: `import litellm`
   - Update `TodoListManager.__init__()` signature
   - Update `create_questions_async()` method
   - Update `generate_todolist_async()` method
   - Update all docstrings

2. **`capstone/agent_v2/tests/unit/test_todolist.py`**
   - Update all test mocks
   - Mock `LLMService` instead of `litellm`
   - Update fixtures

## Testing Requirements

### Unit Tests Updates

```python
# tests/unit/test_todolist.py - UPDATED
import pytest
from unittest.mock import AsyncMock, MagicMock
from capstone.agent_v2.planning.todolist import TodoListManager
from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock()
    return service


@pytest.fixture
def todolist_manager(tmp_path, mock_llm_service):
    """Create TodoListManager with mock service."""
    return TodoListManager(
        todolist_dir=str(tmp_path / "todolists"),
        llm_service=mock_llm_service
    )


class TestTodoListManagerInitialization:
    """Test TodoListManager initialization."""
    
    def test_init_with_llm_service(self, tmp_path, mock_llm_service):
        """Test initialization with LLMService."""
        manager = TodoListManager(
            todolist_dir=str(tmp_path / "todolists"),
            llm_service=mock_llm_service
        )
        
        assert manager.llm_service is mock_llm_service
        assert manager.todolist_dir.exists()


class TestClarificationQuestions:
    """Test clarification question generation."""
    
    @pytest.mark.asyncio
    async def test_create_questions_uses_llm_service(
        self, 
        todolist_manager,
        mock_llm_service
    ):
        """Test that question generation uses LLMService."""
        # Mock service response
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"questions": ["What is X?", "How should Y work?"]}',
            "usage": {"total_tokens": 100}
        }
        
        questions = await todolist_manager.create_questions_async(
            mission="Create a web API",
            tools_desc="Tools: file_write, shell"
        )
        
        # Verify questions returned
        assert len(questions) == 2
        assert "What is X?" in questions
        
        # Verify LLMService was called
        mock_llm_service.complete.assert_called_once()
        
        # Verify model alias used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
    
    @pytest.mark.asyncio
    async def test_create_questions_with_custom_model(
        self,
        todolist_manager,
        mock_llm_service
    ):
        """Test question generation with custom model."""
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"questions": ["Q1?"]}',
            "usage": {"total_tokens": 50}
        }
        
        await todolist_manager.create_questions_async(
            mission="Test",
            tools_desc="Tools",
            model="powerful"  # Override
        )
        
        # Verify custom model used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "powerful"
    
    @pytest.mark.asyncio
    async def test_create_questions_handles_failure(
        self,
        todolist_manager,
        mock_llm_service
    ):
        """Test error handling when LLM fails."""
        # Mock failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "API timeout"
        }
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to generate questions"):
            await todolist_manager.create_questions_async(
                mission="Test",
                tools_desc="Tools"
            )


class TestTodoListGeneration:
    """Test todo list generation."""
    
    @pytest.mark.asyncio
    async def test_generate_todolist_uses_llm_service(
        self,
        todolist_manager,
        mock_llm_service
    ):
        """Test that todolist generation uses LLMService."""
        # Mock service response
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '''{
                "steps": [
                    {
                        "position": 1,
                        "description": "Create API structure",
                        "depends_on": [],
                        "tool_call": "file_write"
                    }
                ],
                "open_questions": []
            }''',
            "usage": {"total_tokens": 200}
        }
        
        todolist = await todolist_manager.generate_todolist_async(
            mission="Create API",
            tools_desc="Tools: file_write",
            answers={"Q1": "Answer1"}
        )
        
        # Verify todolist created
        assert len(todolist.steps) == 1
        assert todolist.steps[0].description == "Create API structure"
        
        # Verify LLMService was called
        mock_llm_service.complete.assert_called_once()
        
        # Verify "fast" model used for structured task
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "fast"
    
    @pytest.mark.asyncio
    async def test_generate_todolist_with_custom_model(
        self,
        todolist_manager,
        mock_llm_service
    ):
        """Test todolist generation with custom model."""
        mock_llm_service.complete.return_value = {
            "success": True,
            "content": '{"steps": [], "open_questions": []}',
            "usage": {"total_tokens": 50}
        }
        
        await todolist_manager.generate_todolist_async(
            mission="Test",
            tools_desc="Tools",
            answers={},
            model="main"  # Override to main instead of fast
        )
        
        # Verify custom model used
        call_args = mock_llm_service.complete.call_args
        assert call_args.kwargs["model"] == "main"
    
    @pytest.mark.asyncio
    async def test_generate_todolist_handles_failure(
        self,
        todolist_manager,
        mock_llm_service
    ):
        """Test error handling when todolist generation fails."""
        # Mock failure
        mock_llm_service.complete.return_value = {
            "success": False,
            "error": "Rate limit exceeded"
        }
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to generate todolist"):
            await todolist_manager.generate_todolist_async(
                mission="Test",
                tools_desc="Tools",
                answers={}
            )
```

## Validation Checklist

- [x] Constructor accepts `llm_service` parameter
- [x] No `import litellm` in todolist.py
- [x] No direct `litellm.acompletion()` calls
- [x] `extract_clarification_questions()` uses `llm_service.complete()`
- [x] `create_todolist()` uses `llm_service.complete()`
- [x] No hardcoded model names
- [x] "main" model used for clarification questions
- [x] "fast" model used for todo generation
- [x] Model override parameters work
- [x] Type annotations complete
- [x] Docstrings updated
- [x] All tests updated and passing
- [x] Code formatted (no issues found)
- [x] No linter errors

## Definition of Done

- [x] Code refactored to use LLMService
- [x] No direct litellm usage
- [x] Constructor accepts llm_service
- [x] Model aliases used ("main", "fast")
- [x] All tests updated and passing
- [x] Type hints complete
- [x] Docstrings updated
- [x] Code formatted
- [x] Linting clean
- [x] TodoListManager behavior verified unchanged

## Next Steps

After this story:
1. Story 6: Update AgentFactory to inject LLMService everywhere

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.5

### File List
**Modified Files:**
- `capstone/agent_v2/planning/todolist.py` - Refactored to use LLMService
- `tests/unit/test_todolist.py` - Updated all tests to use mock LLMService

### Change Log
1. **todolist.py**
   - Removed `import litellm` (line 9)
   - Added `import structlog` and `from capstone.agent_v2.services.llm_service import LLMService`
   - Updated `TodoListManager.__init__()` to accept `llm_service: Optional[LLMService]` parameter
   - Added `self.logger = structlog.get_logger()` to constructor
   - Refactored `extract_clarification_questions()` to use `llm_service.complete()` with "main" model
   - Refactored `create_todolist()` to use `llm_service.complete()` with "fast" model
   - Added comprehensive logging and error handling
   - Added model override parameters to both methods
   - Updated all docstrings with proper documentation

2. **test_todolist.py**
   - Added `mock_llm_service` pytest fixture using `AsyncMock`
   - Updated all test functions to accept `mock_llm_service` fixture
   - Replaced litellm mocking with LLMService mocking
   - Fixed `test_todolist_to_dict_and_to_json_roundtrip` to use new TodoItem structure
   - Updated `test_create_todolist_writes_file_and_returns_object` to verify model alias usage
   - Fixed TodoItem instantiation to use `acceptance_criteria` and `dependencies` instead of deprecated `tool` and `parameters`

### Completion Notes
- All 10 tests pass successfully
- No hardcoded model names remain in production code
- LLMService provides centralized configuration and retry logic
- Model strategy: "main" for reasoning, "fast" for structured generation
- Backwards compatibility maintained with Optional[LLMService] parameter
- Comprehensive error handling and logging added

---

**Story Created:** 2025-11-11  
**Last Updated:** 2025-11-11  
**Assigned To:** James (Dev Agent)  
**Reviewer:** TBD

