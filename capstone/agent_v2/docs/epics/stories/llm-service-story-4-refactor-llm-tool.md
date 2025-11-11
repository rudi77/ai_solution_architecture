# Story 4: Refactor LLMTool to Use LLMService

**Epic:** LLM Service Consolidation & Modernization  
**Story ID:** LLM-SERVICE-004  
**Status:** Done  
**Priority:** High  
**Estimated Effort:** 2-3 days  
**Dependencies:** Story 1 (LLMService created)

## Story Description

Update `LLMTool` to use `LLMService` instead of raw `litellm` module. Change constructor signature to accept service instance, update execute method to use service's generate method, and update all related tests.

## User Story

**As a** developer maintaining tools  
**I want** LLMTool to use LLMService for text generation  
**So that** LLM calls are centralized and benefit from unified configuration and retry logic

## Acceptance Criteria

### Functional Requirements

1. **Constructor Changes**
   - [x] Update `__init__()` signature:
     - OLD: `__init__(self, llm, model: str = "gpt-4.1")`
     - NEW: `__init__(self, llm_service: LLMService, model_alias: str = "main")`
   - [x] Store `llm_service` as instance attribute
   - [x] Store `model_alias` instead of hardcoded model name
   - [x] Update docstring

2. **Execute Method Refactoring**
   - [x] Remove direct `litellm.acompletion()` call (line ~136)
   - [x] Use `llm_service.generate()` method instead
   - [x] Remove `import litellm` from file
   - [x] Pass `model_alias` to service
   - [x] Handle service response format

3. **Response Handling**
   - [x] Adapt to `LLMService.generate()` response format
   - [x] Extract `generated_text` from result
   - [x] Extract token usage from result
   - [x] Handle success/failure responses

4. **Error Handling**
   - [x] Use service's built-in error handling
   - [x] Return service error information
   - [x] Maintain existing error response format

### Non-Functional Requirements

- [x] Type annotations complete
- [x] Docstrings updated
- [x] All tool tests pass
- [x] No performance degradation

## Technical Details

### Current Code (Before)

```python
# tools/llm_tool.py - CURRENT
import litellm
from capstone.agent_v2.tool import Tool


class LLMTool(Tool):
    """Generic LLM tool for natural language text generation"""
    
    def __init__(self, llm, model: str = "gpt-4.1"):
        """
        Initialize LLMTool with an LLM instance.
        
        Args:
            llm: The LLM instance (typically litellm or a configured LLM provider)
            model: The LLM model to use (default: "gpt-4.1")
        """
        self.llm = llm
        self.model = model
        self.logger = structlog.get_logger()
    
    async def execute(
        self, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None, 
        max_tokens: int = 500, 
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute LLM text generation."""
        start_time = time.time()
        
        try:
            # Build full prompt with context
            if context:
                context_str = self._serialize_context(context)
                full_prompt = f"""Context Data:
{context_str}

Task: {prompt}
"""
            else:
                full_prompt = prompt
            
            # Call LLM using litellm.acompletion
            response = await litellm.acompletion(  # Direct call
                model=self.model,  # Hardcoded model
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Extract text and token counts
            generated_text = response.choices[0].message.content
            usage = response.usage if hasattr(response, 'usage') else {}
            # ... rest of method
```

### Refactored Code (After)

```python
# tools/llm_tool.py - REFACTORED
from typing import Any, Dict, Optional
import structlog

from capstone.agent_v2.tool import Tool
from capstone.agent_v2.services.llm_service import LLMService


class LLMTool(Tool):
    """Generic LLM tool for natural language text generation using LLMService."""
    
    def __init__(self, llm_service: LLMService, model_alias: str = "main"):
        """
        Initialize LLMTool with LLMService.
        
        Args:
            llm_service: The centralized LLM service
            model_alias: Model alias from config (default: "main")
        """
        self.llm_service = llm_service
        self.model_alias = model_alias
        self.logger = structlog.get_logger()
    
    @property
    def name(self) -> str:
        return "llm_generate"
    
    @property
    def description(self) -> str:
        return (
            "Use the LLM to generate natural language text based on a prompt. "
            "Useful for: formulating user responses, summarizing information, "
            "formatting data, translating content, creative writing."
        )
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Override to provide detailed parameter descriptions"""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt/instruction for the LLM"
                },
                "context": {
                    "type": "object",
                    "description": "Structured data to include as context (e.g., search results, document lists)"
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum response length in tokens (default: 500)"
                },
                "temperature": {
                    "type": "number",
                    "description": "Creativity control from 0.0 (deterministic) to 1.0 (creative) (default: 0.7)"
                }
            },
            "required": ["prompt"]
        }
    
    async def execute(
        self, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None, 
        max_tokens: int = 500, 
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute LLM text generation using LLMService.
        
        Args:
            prompt: The prompt/instruction for the LLM
            context: Optional structured data to include as context
            max_tokens: Maximum response length (default: 500)
            temperature: Creativity control 0.0-1.0 (default: 0.7)
            
        Returns:
            Dictionary with:
            - success: True if generation succeeded, False otherwise
            - generated_text: The generated text (if successful)
            - tokens_used: Total tokens consumed
            - prompt_tokens: Tokens in the prompt
            - completion_tokens: Tokens in the completion
            - error: Error message (if failed)
            - type: Error type (if failed)
            - hints: Suggestions for fixing errors (if failed)
            
        Example:
            >>> tool = LLMTool(llm_service=llm_service)
            >>> result = await tool.execute(
            ...     prompt="Summarize this data",
            ...     context={"documents": [{"title": "doc1.pdf", "chunks": 214}]}
            ... )
            >>> print(result["generated_text"])
        """
        self.logger.info(
            "llm_generate_started",
            tool="llm_generate",
            has_context=context is not None
        )
        
        try:
            # Use LLMService.generate() method
            result = await self.llm_service.generate(
                prompt=prompt,
                context=context,
                model=self.model_alias,  # Use configured alias
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            # Check if generation succeeded
            if not result.get("success"):
                self.logger.error(
                    "llm_generate_failed",
                    error=result.get("error"),
                    error_type=result.get("error_type")
                )
                
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "type": result.get("error_type", "UnknownError"),
                    "hints": self._get_error_hints(
                        result.get("error_type", ""),
                        result.get("error", "")
                    )
                }
            
            # Extract data from successful result
            generated_text = result.get("generated_text") or result.get("content")
            usage = result.get("usage", {})
            
            self.logger.info(
                "llm_generate_completed",
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=result.get("latency_ms", 0)
            )
            
            return {
                "success": True,
                "generated_text": generated_text,
                "tokens_used": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
            }
            
        except Exception as e:
            # Catch any unexpected errors
            error_type = type(e).__name__
            error_msg = str(e)
            
            self.logger.error(
                "llm_generate_exception",
                error_type=error_type,
                error=error_msg[:200]
            )
            
            return {
                "success": False,
                "error": error_msg,
                "type": error_type,
                "hints": self._get_error_hints(error_type, error_msg)
            }
    
    def _get_error_hints(self, error_type: str, error_msg: str) -> list:
        """
        Generate helpful hints based on error type.
        
        Args:
            error_type: The type of exception
            error_msg: The error message
            
        Returns:
            List of hint strings
        """
        hints = ["Check LLM configuration", "Verify API credentials"]
        
        # Token limit errors
        if "token" in error_msg.lower() or "length" in error_msg.lower():
            hints.append("Reduce prompt size or increase max_tokens parameter")
        
        # Network/timeout errors
        if error_type in ["TimeoutError", "ConnectionError", "ClientError"]:
            hints.append("Retry the request")
            hints.append("Check network connectivity")
        
        # Authentication errors
        if "auth" in error_msg.lower() or "api key" in error_msg.lower():
            hints.append("Verify API key is set correctly")
        
        return hints
```

## Files to Modify

1. **`capstone/agent_v2/tools/llm_tool.py`**
   - Add import: `from capstone.agent_v2.services.llm_service import LLMService`
   - Remove import: `import litellm`
   - Update `__init__()` signature
   - Update `execute()` method
   - Update all docstrings

2. **`capstone/agent_v2/tests/test_llm_tool.py`**
   - Update all test mocks
   - Mock `LLMService` instead of `litellm`
   - Update fixtures

## Testing Requirements

### Unit Tests Updates

```python
# tests/test_llm_tool.py - UPDATED
import pytest
from unittest.mock import AsyncMock, MagicMock
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService for testing."""
    service = MagicMock(spec=LLMService)
    service.generate = AsyncMock()
    return service


@pytest.fixture
def llm_tool(mock_llm_service):
    """Create LLMTool with mock service."""
    return LLMTool(llm_service=mock_llm_service, model_alias="main")


class TestLLMToolInitialization:
    """Test LLMTool initialization."""
    
    def test_init_with_llm_service(self, mock_llm_service):
        """Test initialization with LLMService."""
        tool = LLMTool(llm_service=mock_llm_service, model_alias="fast")
        
        assert tool.llm_service is mock_llm_service
        assert tool.model_alias == "fast"
        assert tool.name == "llm_generate"


class TestLLMToolExecution:
    """Test LLMTool execute method."""
    
    @pytest.mark.asyncio
    async def test_successful_generation_without_context(self, llm_tool, mock_llm_service):
        """Test successful text generation without context."""
        # Mock service response
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Generated response text",
            "content": "Generated response text",
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 50,
                "completion_tokens": 100
            },
            "latency_ms": 250
        }
        
        result = await llm_tool.execute(prompt="What is AI?")
        
        # Verify success
        assert result["success"] is True
        assert result["generated_text"] == "Generated response text"
        assert result["tokens_used"] == 150
        assert result["prompt_tokens"] == 50
        assert result["completion_tokens"] == 100
        
        # Verify service was called correctly
        mock_llm_service.generate.assert_called_once()
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["prompt"] == "What is AI?"
        assert call_args.kwargs["model"] == "main"
    
    @pytest.mark.asyncio
    async def test_successful_generation_with_context(self, llm_tool, mock_llm_service):
        """Test text generation with context data."""
        context = {
            "documents": [
                {"title": "doc1.pdf", "chunks": 120},
                {"title": "doc2.pdf", "chunks": 85}
            ]
        }
        
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Summary of documents",
            "usage": {"total_tokens": 200, "prompt_tokens": 150, "completion_tokens": 50}
        }
        
        result = await llm_tool.execute(
            prompt="List the documents",
            context=context
        )
        
        assert result["success"] is True
        assert "Summary" in result["generated_text"]
        
        # Verify context was passed
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["context"] == context
    
    @pytest.mark.asyncio
    async def test_handles_service_failure(self, llm_tool, mock_llm_service):
        """Test handling of LLM service failures."""
        # Mock service failure
        mock_llm_service.generate.return_value = {
            "success": False,
            "error": "API Error: Rate limit exceeded",
            "error_type": "RateLimitError"
        }
        
        result = await llm_tool.execute(prompt="Test prompt")
        
        # Verify error is handled gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Rate limit" in result["error"]
        assert "hints" in result
    
    @pytest.mark.asyncio
    async def test_passes_temperature_parameter(self, llm_tool, mock_llm_service):
        """Test that temperature parameter is passed to service."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Test response",
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}
        }
        
        await llm_tool.execute(
            prompt="Test prompt",
            temperature=0.3
        )
        
        # Verify temperature was passed
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["temperature"] == 0.3
    
    @pytest.mark.asyncio
    async def test_passes_max_tokens_parameter(self, llm_tool, mock_llm_service):
        """Test that max_tokens parameter is passed to service."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Test response",
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}
        }
        
        await llm_tool.execute(
            prompt="Test prompt",
            max_tokens=1000
        )
        
        # Verify max_tokens was passed
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["max_tokens"] == 1000
    
    @pytest.mark.asyncio
    async def test_uses_configured_model_alias(self, mock_llm_service):
        """Test that tool uses configured model alias."""
        tool = LLMTool(llm_service=mock_llm_service, model_alias="powerful")
        
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Response",
            "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
        }
        
        await tool.execute(prompt="Test")
        
        # Verify correct alias used
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["model"] == "powerful"


class TestLLMToolErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self, llm_tool, mock_llm_service):
        """Test handling of unexpected exceptions."""
        # Mock to raise exception
        mock_llm_service.generate.side_effect = RuntimeError("Unexpected error")
        
        result = await llm_tool.execute(prompt="Test")
        
        assert result["success"] is False
        assert result["type"] == "RuntimeError"
        assert "Unexpected error" in result["error"]
```

## Validation Checklist

- [ ] Constructor signature updated
- [ ] `llm_service` parameter accepted
- [ ] `model_alias` parameter accepted (replaces hardcoded model)
- [ ] No `import litellm` in llm_tool.py
- [ ] No direct `litellm.acompletion()` calls
- [ ] Uses `llm_service.generate()` method
- [ ] Response format handled correctly
- [ ] Error handling uses service errors
- [ ] All test mocks updated
- [ ] All tests pass
- [ ] Type annotations complete
- [ ] Docstrings updated
- [ ] Code formatted (Black)
- [ ] No linter errors (Ruff)

## Definition of Done

- [x] Code refactored to use LLMService
- [x] No direct litellm usage
- [x] Constructor accepts llm_service
- [x] Model alias system used
- [x] All tests updated and passing
- [x] Type hints complete
- [x] Docstrings updated
- [x] Code formatted
- [x] Linting clean
- [x] Tool behavior verified unchanged

## Next Steps

After this story:
1. Story 5: Refactor TodoListManager to use LLMService
2. Story 6: Update AgentFactory to inject LLMService

---

**Story Created:** 2025-11-11  
**Last Updated:** 2025-11-11  
**Assigned To:** TBD  
**Reviewer:** TBD

---

## QA Results

### Review Date: 2025-11-11

### Reviewed By: Quinn (Senior Developer QA)

### Code Quality Assessment

**Overall Grade: Excellent (A)**

This refactoring demonstrates exceptional code quality and engineering discipline. The implementation successfully migrates `LLMTool` from direct `litellm` usage to the centralized `LLMService` while maintaining full backward compatibility and enhancing testability. The code is clean, well-documented, and follows all Python best practices.

**Key Strengths:**
- **Clean Architecture**: Perfect delegation of LLM responsibility to `LLMService`, following Single Responsibility Principle
- **Comprehensive Testing**: 18 unit tests covering all scenarios including edge cases, error handling, and parameter variations
- **Backward Compatibility**: Elegant parameter migration in `_instantiate_tool` prevents breaking existing configurations
- **Type Safety**: Complete type annotations with proper Optional types and return type hints
- **Error Handling**: Robust error handling with helpful user-facing hints based on error types
- **Documentation**: Clear, comprehensive docstrings with examples following Google style
- **Code Simplification**: Removed 48 lines of code by eliminating `_serialize_context` method (now handled by service)

### Refactoring Performed

**No additional refactoring needed.** The developer (James) delivered production-ready code that meets all senior developer standards. The implementation is exemplary.

### Compliance Check

- **Coding Standards**: ✓ **Excellent**
  - PEP 8 compliant (verified via linter)
  - Clean imports, proper structure
  - Meaningful variable names
  - Functions under 30 lines
  - No code duplication

- **Project Structure**: ✓ **Perfect**
  - Files in correct locations
  - Proper module organization
  - Integration tests updated appropriately

- **Testing Strategy**: ✓ **Comprehensive**
  - 18 unit tests, all passing
  - Test coverage includes:
    - Happy path scenarios
    - Error conditions (network, auth, token limits)
    - Parameter handling and defaults
    - Model alias configuration
    - Context handling (dict, string, large contexts)
    - Privacy/logging verification
  - Proper use of fixtures and mocks
  - Integration tests updated (6 files total)

- **All ACs Met**: ✓ **Complete**
  - Constructor signature updated correctly
  - `litellm` import removed
  - Uses `LLMService.generate()` method
  - Response format handled correctly
  - Error handling delegated to service
  - All 18 tests passing (+ 48 integration tests)

### Improvements Checklist

All items have been handled by the developer. No additional improvements required.

- [x] Constructor refactored to accept `llm_service` (llm_tool.py)
- [x] Model alias system implemented (llm_tool.py)
- [x] Direct litellm calls removed (llm_tool.py)
- [x] Response format handling updated (llm_tool.py)
- [x] All unit tests updated with LLMService mocks (test_llm_tool.py)
- [x] Integration tests updated (test_llm_tool_integration.py, test_rag_synthesis.py)
- [x] Agent factory updated for backward compatibility (agent_factory.py)
- [x] Agent.create_agent updated (agent.py)
- [x] Parameter migration logic added for smooth transition (_instantiate_tool)
- [x] Type hints complete and accurate
- [x] Docstrings updated with correct examples
- [x] All linter checks passing

### Security Review

**Status: ✓ No Security Concerns**

- **API Key Handling**: Not handled by LLMTool (delegated to LLMService) ✓
- **Input Validation**: Parameters validated by LLMService ✓
- **Privacy**: Logging properly excludes sensitive prompt/response content ✓
  - Test `test_logging_metadata_not_full_text` explicitly verifies this
- **Error Messages**: Error hints don't leak sensitive information ✓

### Performance Considerations

**Status: ✓ Performance Optimized**

- **No Performance Degradation**: Delegation to LLMService maintains same performance characteristics
- **Improved Efficiency**: Removed redundant context serialization (handled by service layer)
- **Resource Management**: Proper async/await patterns maintained
- **Service Benefits**: Now leverages LLMService's retry logic and connection pooling
- **Token Usage Tracking**: Properly extracts and returns token usage for monitoring

### Test Execution Results

```
Unit Tests (test_llm_tool.py):           18 passed ✓
Agent Factory Tests:                     28 passed, 3 skipped ✓
RAG Integration Tests:                   6 passed ✓
Agent LLM Service Tests:                 12 passed ✓
---
Total:                                   64 passed, 3 skipped, 0 failed
Linter Errors:                           0
```

### Technical Excellence Highlights

1. **Dependency Injection**: Perfect implementation of DI pattern with `llm_service` parameter
2. **Fallback Logic**: Elegant handling of `generated_text` vs `content` fields (line 136)
3. **Error Context**: Maintains all error context while adding helpful hints
4. **Test Design**: Excellent use of fixtures and proper async test patterns
5. **Migration Path**: Smooth backward compatibility ensures zero-downtime deployment

### Code Examples Reviewed

**Before (Old Pattern):**
```python
response = await litellm.acompletion(
    model=self.model,
    messages=[{"role": "user", "content": full_prompt}],
    max_tokens=max_tokens,
    temperature=temperature
)
```

**After (New Pattern):**
```python
result = await self.llm_service.generate(
    prompt=prompt,
    context=context,
    model=self.model_alias,
    max_tokens=max_tokens,
    temperature=temperature,
    **kwargs
)
```

**Why**: Centralizes LLM interaction logic, enables configuration-driven model selection, provides retry logic, and improves testability.

**How**: Reduces coupling, improves maintainability, and aligns with service-oriented architecture patterns.

### Final Status

**✓ APPROVED - READY FOR DONE**

This implementation sets the bar for refactoring quality. The developer demonstrated:
- Deep understanding of service patterns
- Comprehensive testing discipline  
- Attention to backward compatibility
- Clean code principles
- Professional documentation

**Recommendation**: Mark story as **Done** and use this implementation as a reference for future refactoring stories (Stories 5 & 6).

### Notes for Next Stories

For Story 5 (TodoListManager) and Story 6 (AgentFactory updates):
1. Follow this same pattern for service integration
2. Maintain the same level of test coverage
3. Implement similar backward compatibility handling
4. Keep the same documentation quality standards

---

**QA Reviewed By:** Quinn  
**QA Date:** 2025-11-11  
**Hours Reviewed:** 1.5 hours  
**Review Status:** APPROVED ✓

