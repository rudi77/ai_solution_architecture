# Story 1.6: Implement Infrastructure - LLM Service Adapter

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.6  
**Status**: Pending  
**Priority**: High  
**Estimated Points**: 2  
**Dependencies**: Story 1.2 (Protocol Interfaces)

---

## User Story

As a **developer**,  
I want **LLM service relocated from Agent V2 with protocol implementation**,  
so that **core domain can make LLM calls via abstraction**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/infrastructure/llm/openai_service.py`
2. ✅ Relocate code from `capstone/agent_v2/services/llm_service.py` with minimal changes
3. ✅ Implement `LLMProviderProtocol` interface
4. ✅ Preserve all Agent V2 functionality:
   - Model aliases (main, fast, powerful, legacy)
   - Parameter mapping (GPT-4 vs GPT-5 params)
   - Retry logic with exponential backoff
   - Token usage logging
   - Azure OpenAI support
5. ✅ Configuration via `llm_config.yaml` (same format as Agent V2)
6. ✅ Unit tests with mocked LiteLLM verify parameter mapping
7. ✅ Integration tests with actual LLM API verify completion requests

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 LLMService continues to function independently
- **IV2: Integration Point Verification** - Taskforce LLMService produces identical completion results for same prompts as Agent V2
- **IV3: Performance Impact Verification** - LLM call latency matches Agent V2 (protocol abstraction overhead <1%)

---

## Technical Notes

**Implementation Approach:**

```python
# taskforce/src/taskforce/infrastructure/llm/openai_service.py
import litellm
from typing import Dict, Any, List
from taskforce.core.interfaces.llm import LLMProviderProtocol

class OpenAIService:
    """LLM service supporting OpenAI and Azure OpenAI via LiteLLM.
    
    Implements LLMProviderProtocol for dependency injection.
    """
    
    def __init__(self, config_path: str = "configs/llm_config.yaml"):
        # Relocate initialization logic from agent_v2/services/llm_service.py
        self.config = self._load_config(config_path)
        self._initialize_provider()
    
    async def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **params
    ) -> Dict[str, Any]:
        """Complete chat conversation."""
        # Relocate logic from agent_v2/services/llm_service.py
        ...
    
    async def generate(
        self,
        model: str,
        prompt: str,
        **params
    ) -> str:
        """Generate completion from prompt."""
        ...
    
    def _map_parameters_for_model(self, model: str, params: Dict) -> Dict:
        """Map GPT-4 params to GPT-5 params if needed."""
        # Preserve parameter mapping logic
        ...
```

**Reference File:**
- `capstone/agent_v2/services/llm_service.py` - Copy/adapt entire LLMService class

**Key Features to Preserve:**
- Model alias resolution (main → gpt-4, fast → gpt-4-mini, etc.)
- GPT-4 → GPT-5 parameter mapping (temperature → effort, etc.)
- Retry logic with exponential backoff
- Token usage and latency logging
- Azure OpenAI endpoint support

---

## Configuration

Copy `capstone/agent_v2/configs/llm_config.yaml` to `taskforce/configs/llm_config.yaml`:

```yaml
models:
  main:
    name: "gpt-4"
    provider: "openai"
  fast:
    name: "gpt-4-mini"
    provider: "openai"
  powerful:
    name: "gpt-5"
    provider: "openai"

providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"

retry:
  max_attempts: 3
  backoff_multiplier: 2
```

---

## Testing Strategy

**Unit Tests:**
```python
# tests/unit/infrastructure/test_llm_service.py
from unittest.mock import patch, AsyncMock
from taskforce.infrastructure.llm.openai_service import OpenAIService

@pytest.mark.asyncio
async def test_parameter_mapping_gpt5():
    service = OpenAIService()
    
    # Test that temperature is mapped to effort for GPT-5
    params = {"temperature": 0.7, "top_p": 0.9}
    mapped = service._map_parameters_for_model("gpt-5", params)
    
    assert "effort" in mapped
    assert "reasoning" in mapped
    assert "temperature" not in mapped

@pytest.mark.asyncio
@patch('litellm.acompletion')
async def test_completion_with_retry(mock_completion):
    mock_completion.side_effect = [
        Exception("Rate limit"),  # First attempt fails
        {"choices": [{"message": {"content": "Success"}}]}  # Second attempt succeeds
    ]
    
    service = OpenAIService()
    result = await service.complete("main", [{"role": "user", "content": "Hi"}])
    
    assert result["choices"][0]["message"]["content"] == "Success"
    assert mock_completion.call_count == 2
```

**Integration Tests:**
```python
# tests/integration/test_llm_service_integration.py
@pytest.mark.asyncio
@pytest.mark.integration
async def test_actual_llm_call():
    """Test with actual OpenAI API (requires API key)."""
    service = OpenAIService()
    
    result = await service.complete(
        "fast",
        [{"role": "user", "content": "Say 'test passed' in exactly those words."}]
    )
    
    assert "test passed" in result["choices"][0]["message"]["content"].lower()
```

---

## Definition of Done

- [ ] OpenAIService implements LLMProviderProtocol
- [ ] All Agent V2 llm_service.py logic relocated
- [ ] Configuration file copied to taskforce/configs/
- [ ] Unit tests achieve ≥80% coverage
- [ ] Integration tests verify actual LLM calls
- [ ] Produces identical results to Agent V2 for same prompts
- [ ] Performance overhead <1%
- [ ] Code review completed
- [ ] Code committed to version control

