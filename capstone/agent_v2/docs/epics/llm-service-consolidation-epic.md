# Epic: LLM Service Consolidation & Modernization - Brownfield Enhancement

## Epic Goal

Create a centralized `LLMService` that encapsulates all LiteLLM interactions, eliminates scattered configuration, and enables modern LLM features (including GPT-5 support) through a single, unified configuration file.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- LiteLLM is directly imported and called in multiple locations:
  - `agent.py` - Direct `litellm.acompletion()` calls for message compression and thought generation
  - `tools/llm_tool.py` - Direct `litellm.acompletion()` call for text generation
  - `planning/todolist.py` - Direct `litellm.acompletion()` calls for clarification questions and todo list generation
  - `agent_factory.py` - Returns raw `litellm` module as LLM instance
- Model names are hardcoded throughout the codebase ("gpt-4.1", "gpt-4.1-mini")
- No centralized configuration for LLM parameters (temperature, max_tokens, retry policies, etc.)
- Package versions: `litellm==1.7.7.0` (old), `openai>=1.0`

**Technology stack:**
- Python 3.11+ with async/await patterns
- LiteLLM for unified LLM API access
- OpenAI SDK as underlying provider
- structlog for logging
- YAML for configuration

**Integration points:**
- `Agent` class uses LLM for message compression and ReAct thought loops
- `LLMTool` provides LLM access to agents as a tool
- `TodoListManager` uses LLM for planning and task breakdown
- `agent_factory.py` provides LLM instances to created agents
- All CLI commands indirectly depend on LLM functionality

### Enhancement Details

**What's being added/changed:**

1. **Centralized LLMService Class:**
   - Create new `services/llm_service.py` module
   - `LLMService` class encapsulates all LiteLLM interactions
   - Supports configurable models, parameters, retry logic, and error handling
   - **Model-aware parameter mapping**: Automatically adapts parameters based on model type
     - GPT-4/4.1: Uses traditional parameters (temperature, top_p, max_tokens)
     - GPT-5: Uses new parameters (effort, reasoning) and ignores deprecated parameters
   - Single initialization point with configuration
   - Provides async methods: `complete()`, `generate()`, `chat()`

2. **Unified Configuration:**
   - Create `configs/llm_config.yaml` for LLM settings
   - Configuration includes:
     - Default model and model aliases (e.g., "fast" → "gpt-4.1-mini", "main" → "gpt-5")
     - **Model-specific parameters**: Different parameter sets for GPT-4 vs GPT-5
       - GPT-4/4.1: temperature, top_p, max_tokens, frequency_penalty, presence_penalty
       - GPT-5: effort, reasoning, max_tokens (temperature fixed at 1.0, not configurable)
     - Retry policies and timeout settings
     - Provider-specific settings (OpenAI, Azure, etc.)
   - Load configuration once at application startup
   - Environment variable overrides for API keys

3. **Package Upgrades:**
   - Upgrade `litellm` to latest version (>=1.50.0 for GPT-5 support)
   - Upgrade `openai` to latest compatible version (>=1.50.0)
   - Verify compatibility with existing async patterns

4. **Refactor All Call Sites:**
   - Replace all direct `litellm.acompletion()` calls with `llm_service` methods
   - Remove hardcoded model names
   - Inject `LLMService` instance through dependency injection
   - Update `agent_factory.py` to create and inject `LLMService`

**How it integrates:**
- `LLMService` initialized once in `agent_factory.py` from config
- Passed to `Agent`, `LLMTool`, and `TodoListManager` during instantiation
- All components use same service instance (shared configuration)
- Backward compatible: Existing agent creation flows unchanged
- Configuration can be overridden per-agent if needed via YAML

**Success criteria:**
- Zero direct `litellm.acompletion()` calls outside `LLMService`
- All model names sourced from configuration
- Single `configs/llm_config.yaml` controls all LLM behavior
- Can switch to GPT-5 by changing one config value
- All existing tests pass with minimal modifications
- No performance degradation
- Improved error handling and retry logic centralized

## Stories

### Story 1: Create LLMService with Configuration Loading

**Description:** Create the `LLMService` class and YAML configuration infrastructure. Implement configuration loading, model aliasing, and basic LLM interaction methods with retry logic and error handling.

**Acceptance Criteria:**
- New module: `capstone/agent_v2/services/llm_service.py`
- New config: `capstone/agent_v2/configs/llm_config.yaml`
- `LLMService` class with methods:
  - `__init__(config_path: str)` - Load configuration
  - `async complete(messages, model=None, **kwargs)` - Generic completion
  - `async generate(prompt, context=None, model=None, **kwargs)` - Single-turn generation
  - `_map_parameters_for_model(model: str, params: dict) -> dict` - Model-aware parameter mapping
- Configuration schema supports:
  - `default_model` and `models` dictionary with aliases
  - **Model-specific parameters**: `model_params` section with per-model or per-family configuration
  - Legacy `default_params` for backward compatibility
  - `retry_policy` (max_attempts, backoff)
  - `timeout` settings
- Model alias resolution (e.g., "fast" → actual model name)
- **GPT-5 parameter adaptation**: Automatically converts temperature/top_p to effort/reasoning for GPT-5 models
- Environment variable support for API keys (`OPENAI_API_KEY`, etc.)
- Comprehensive logging using structlog

**Technical Details:**
```yaml
# Example llm_config.yaml structure
default_model: "main"
models:
  main: "gpt-4.1"
  fast: "gpt-4.1-mini"
  powerful: "gpt-5"  # GPT-5 with new API

# Model-specific parameter configurations
model_params:
  # GPT-4 family uses traditional parameters
  gpt-4:
    temperature: 0.7
    top_p: 1.0
    max_tokens: 2000
    frequency_penalty: 0.0
    presence_penalty: 0.0
  
  gpt-4.1:
    temperature: 0.7
    top_p: 1.0
    max_tokens: 2000
  
  gpt-4.1-mini:
    temperature: 0.7
    max_tokens: 1500
  
  # GPT-5 family uses new reasoning parameters
  gpt-5:
    effort: "medium"        # low, medium, high
    reasoning: "balanced"   # minimal, balanced, deep
    max_tokens: 4000
    # Note: temperature not supported (fixed at 1.0)
    # Note: top_p not supported for GPT-5

# Legacy default_params (for backward compatibility)
default_params:
  temperature: 0.7
  max_tokens: 2000

retry_policy:
  max_attempts: 3
  backoff_multiplier: 2
  timeout: 30

providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
```

**GPT-5 Parameter Mapping Logic:**
```python
def _map_parameters_for_model(self, model: str, params: dict) -> dict:
    """Map parameters based on model family."""
    # Detect GPT-5 models
    if "gpt-5" in model.lower():
        mapped = {}
        
        # Max tokens is universal
        if "max_tokens" in params:
            mapped["max_tokens"] = params["max_tokens"]
        
        # Map temperature to effort (approximate mapping)
        if "temperature" in params:
            temp = params["temperature"]
            if temp < 0.3:
                mapped["effort"] = "low"
            elif temp < 0.7:
                mapped["effort"] = "medium"
            else:
                mapped["effort"] = "high"
        
        # Use configured effort/reasoning if available
        if "effort" in params:
            mapped["effort"] = params["effort"]
        if "reasoning" in params:
            mapped["reasoning"] = params["reasoning"]
        
        # Ignore deprecated parameters (temperature, top_p, logprobs)
        # Log warning if they were provided
        
        return mapped
    else:
        # GPT-4 and other models: use traditional parameters
        return {k: v for k, v in params.items() 
                if k in ["temperature", "top_p", "max_tokens", 
                         "frequency_penalty", "presence_penalty"]}
```

**Files to create:**
- `capstone/agent_v2/services/__init__.py`
- `capstone/agent_v2/services/llm_service.py`
- `capstone/agent_v2/configs/llm_config.yaml`

**Files to modify:**
- None (standalone story)

### Story 2: Upgrade LiteLLM and OpenAI Packages

**Description:** Upgrade `litellm` and `openai` packages to latest versions to enable GPT-5 support and modern features. Verify compatibility with existing async patterns and fix any breaking changes. **Critical: Validate GPT-5 API parameter changes.**

**Acceptance Criteria:**
- `pyproject.toml` updated:
  - `litellm>=1.50.0` (or latest stable with GPT-5 support)
  - `openai>=1.50.0` (or latest stable with GPT-5 API)
- All existing tests pass after upgrade
- No breaking changes in async patterns
- **Verify GPT-5 model availability** in updated litellm
- **Test GPT-5 parameter behavior**:
  - Confirm `temperature` parameter causes error or is ignored
  - Confirm `effort` and `reasoning` parameters work
  - Validate 400 Bad Request response for invalid parameters
- Update `uv.lock` file
- Document any API changes discovered

**Technical Details:**
- Research latest compatible versions of litellm and openai
- Test upgrade in isolated environment first
- Check for deprecated APIs or breaking changes
- Update any affected code patterns
- Verify async/await behavior unchanged
- **Create test script to validate GPT-5 API behavior**:
```python
# test_gpt5_params.py
import asyncio
import litellm

async def test_gpt5_params():
    # Test 1: Traditional parameters (should fail or be ignored)
    try:
        response = await litellm.acompletion(
            model="gpt-5",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.5  # Should cause issue
        )
        print("⚠️ Temperature accepted (unexpected)")
    except Exception as e:
        print(f"✓ Temperature rejected: {type(e).__name__}")
    
    # Test 2: New GPT-5 parameters (should work)
    try:
        response = await litellm.acompletion(
            model="gpt-5",
            messages=[{"role": "user", "content": "Hello"}],
            effort="medium",
            reasoning="balanced"
        )
        print("✓ GPT-5 parameters accepted")
    except Exception as e:
        print(f"✗ GPT-5 parameters rejected: {e}")

asyncio.run(test_gpt5_params())
```

**Files to modify:**
- `capstone/agent_v2/pyproject.toml`
- `capstone/agent_v2/uv.lock` (generated)

**Validation:**
- Run full test suite: `pytest capstone/agent_v2/tests/`
- Verify LiteLLM initialization works
- Test basic completion calls with GPT-4 (should still work)
- **Test GPT-5 parameter validation** (run test script)
- Document exact parameter behavior for GPT-5

### Story 3: Refactor Agent Class to Use LLMService

**Description:** Replace direct `litellm.acompletion()` calls in `agent.py` with `LLMService` methods. Inject `LLMService` instance into Agent constructor. Update message compression and thought generation to use service.

**Acceptance Criteria:**
- `Agent.__init__()` accepts `llm_service: LLMService` parameter
- Remove direct `litellm` import from `agent.py`
- Replace `litellm.acompletion()` calls:
  - Line 106: `MessageHistory.compress_history_async()` uses `llm_service.complete()`
  - Line 705: `Agent.get_thought_agent_action_async()` uses `llm_service.complete()`
- Model names sourced from configuration (no hardcoded "gpt-4.1")
- All existing `Agent` tests pass
- Backward compatibility maintained through `agent_factory.py`

**Technical Details:**
- Store `llm_service` as instance attribute: `self.llm_service`
- Update method signatures if needed to accept `llm_service`
- For `MessageHistory.compress_history_async()`:
  - Either pass `llm_service` as parameter, or
  - Store reference when `MessageHistory` is created
- Remove hardcoded model names, use service defaults

**Files to modify:**
- `capstone/agent_v2/agent.py`

**Tests to update:**
- Mock `llm_service` instead of `litellm` in tests
- Update test fixtures if needed

### Story 4: Refactor LLMTool to Use LLMService

**Description:** Update `LLMTool` to use `LLMService` instead of raw `litellm` module. Inject service during tool initialization. Update tool tests to mock service.

**Acceptance Criteria:**
- `LLMTool.__init__()` signature changed:
  - Old: `__init__(self, llm, model: str = "gpt-4.1")`
  - New: `__init__(self, llm_service: LLMService, model_alias: str = "main")`
- Remove direct `litellm.acompletion()` call (line 136)
- Use `llm_service.generate()` method instead
- Remove `import litellm` from `llm_tool.py`
- All `test_llm_tool.py` tests pass with updated mocks

**Technical Details:**
- Store `llm_service` as instance attribute
- Use `model_alias` to reference configured models
- Call `await self.llm_service.generate(prompt, context, model=model_alias, **kwargs)`
- Service handles model resolution and retry logic

**Files to modify:**
- `capstone/agent_v2/tools/llm_tool.py`
- `capstone/agent_v2/tests/test_llm_tool.py`

### Story 5: Refactor TodoListManager to Use LLMService

**Description:** Update `TodoListManager` to use `LLMService` for clarification questions and todo list generation. Remove direct litellm calls and hardcoded model names.

**Acceptance Criteria:**
- `TodoListManager.__init__()` accepts `llm_service: LLMService` parameter
- Remove direct `litellm` import from `todolist.py`
- Replace `litellm.acompletion()` calls:
  - Line 247: `create_questions_async()` uses `llm_service.complete()`
  - Line 354: `generate_todolist_async()` uses `llm_service.complete()`
- Remove hardcoded models ("gpt-4.1", "gpt-4.1-mini")
- Use model aliases: "main" for standard, "fast" for quick tasks
- All todolist tests pass

**Technical Details:**
- Store `llm_service` as instance attribute: `self.llm_service`
- Update `create_questions_async()`:
  ```python
  response = await self.llm_service.complete(
      messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt}
      ],
      model="main",
      response_format={"type": "json_object"}
  )
  ```
- Update `generate_todolist_async()` similarly with model="fast"

**Files to modify:**
- `capstone/agent_v2/planning/todolist.py`
- `capstone/agent_v2/tests/unit/test_todolist.py`

### Story 6: Update Agent Factory to Inject LLMService

**Description:** Modify `agent_factory.py` to create `LLMService` instance and inject it into agents and tools. Update all factory functions to use service. Remove raw litellm module usage.

**Acceptance Criteria:**
- New function: `create_llm_service(config_path: str = None) -> LLMService`
- Update `create_standard_agent()`:
  - Create `LLMService` instance
  - Pass to `LLMTool`, `Agent`, and other components
- Update `create_rag_agent()` similarly
- Update `create_agent_from_config()` to support LLM config path
- Remove `return litellm` from `_create_llm_from_config()`
- Update YAML agent configs to reference LLM config
- All factory tests pass

**Technical Details:**
- Default config path: `capstone/agent_v2/configs/llm_config.yaml`
- Factory creates single `LLMService` instance per agent
- Pass `llm_service` to:
  - `Agent` constructor
  - `LLMTool` constructor
  - `TodoListManager` constructor
- Update agent YAML schema:
```yaml
llm_config:
  config_file: "configs/llm_config.yaml"  # Optional override
  model_override: "powerful"  # Optional per-agent model
```

**Files to modify:**
- `capstone/agent_v2/agent_factory.py`
- `capstone/agent_v2/configs/standard_agent.yaml`
- `capstone/agent_v2/configs/rag_agent.yaml`
- `capstone/agent_v2/tests/test_agent_factory.py`

## Compatibility Requirements

- ✅ **Existing APIs:** Agent creation APIs unchanged (backward compatible through factory)
- ✅ **Configuration:** New config file, existing configs enhanced but not broken
- ✅ **CLI commands:** No changes needed (use factory functions)
- ✅ **Performance impact:** Minimal to positive (better retry logic, connection pooling)
- ✅ **Backward compatibility:** All existing code works with injected service
- ⚠️ **Package upgrades:** May require Python 3.11+ (verify compatibility)

## Risk Mitigation

**Primary Risk:** Package upgrades cause breaking changes in litellm/openai APIs, especially GPT-5 parameter incompatibilities

**Mitigation:**
- Implement Story 2 (package upgrade) early as standalone story
- **Create validation script for GPT-5 parameter behavior** (included in Story 2)
- Test upgrade in isolation before refactoring
- Run full test suite after upgrade
- Document exact GPT-5 parameter behavior through testing
- **Implement model-aware parameter mapping** in LLMService to handle API differences
- Rollback plan: Pin to old versions if major issues found

**Secondary Risk:** Breaking existing agent execution during refactoring

**Mitigation:**
- Implement incrementally (6 stories, each component isolated)
- Update tests alongside code changes
- Run full test suite after each story
- Each story independently testable and committable
- Keep factories working throughout (inject service, but keep old paths temporarily)
- **Automatic parameter adaptation** ensures existing code works with GPT-5

**Tertiary Risk:** GPT-5 parameter mapping produces unexpected behavior

**Mitigation:**
- **Comprehensive logging** of all parameter transformations
- Log warnings when deprecated parameters are filtered
- Configuration option to log full request/response for debugging
- Allow explicit per-model parameter configuration in YAML
- Fallback to GPT-4 models if GPT-5 causes issues
- Document parameter mapping behavior in code comments

**Rollback Plan:**
- Each story is independently committable via Git
- Revert to previous commit if story fails validation
- No database migrations or persistent state changes
- Configuration file additive (doesn't break existing code if not used initially)
- Can easily switch back to GPT-4 models via single config change

## Definition of Done

- ✅ `LLMService` class fully implemented with configuration loading
- ✅ **Model-aware parameter mapping** implemented and tested
- ✅ Single `configs/llm_config.yaml` controls all LLM behavior
- ✅ Zero direct `litellm.acompletion()` calls outside `LLMService`
- ✅ All components (`Agent`, `LLMTool`, `TodoListManager`) use `LLMService`
- ✅ `agent_factory.py` creates and injects `LLMService`
- ✅ Package upgrades complete (`litellm>=1.50.0`, `openai>=1.50.0`)
- ✅ **GPT-5 support verified** with new parameters (`effort`, `reasoning`)
- ✅ **GPT-5 parameter validation** tested (deprecated parameters rejected/ignored)
- ✅ **Automatic parameter adaptation** works for GPT-4 ↔ GPT-5 switching
- ✅ All existing tests pass (unit and integration)
- ✅ No hardcoded model names in codebase
- ✅ Centralized error handling and retry logic
- ✅ Improved logging for all LLM interactions (including parameter mappings)
- ✅ Documentation updated (README, config examples, GPT-5 migration guide)

## Validation Checklist

**Scope Validation:**
- ✅ Epic completable in 6 stories
- ✅ Clear separation of concerns (config, upgrade, refactor components, integrate)
- ✅ Each story independently testable
- ✅ Follows existing patterns (dependency injection, YAML config, async)
- ✅ Integration complexity manageable (one component at a time)

**Risk Assessment:**
- ⚠️ Risk to existing system: MEDIUM (package upgrade + widespread refactoring)
- ✅ Mitigation plan in place (isolated upgrade, incremental refactoring)
- ✅ Rollback plan feasible (Git revert per story)
- ✅ Testing approach: Full test suite validation per story
- ✅ Team has sufficient knowledge (Python, async, litellm)

**Completeness Check:**
- ✅ Epic goal clear and achievable
- ✅ Stories properly scoped and sequenced
- ✅ Success criteria measurable (tests pass, config works, GPT-5 available)
- ✅ Dependencies identified (Story 2 before 3-6, Story 1 parallel)
- ✅ All integration points covered
- ✅ Backward compatibility maintained

## Story Manager Handoff

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is a significant refactoring of an existing Python agent system using async/await patterns and litellm
- Integration points span multiple components:
  - `agent.py` - Core agent with message history and thought loop
  - `tools/llm_tool.py` - LLM tool for agent use
  - `planning/todolist.py` - Planning and task breakdown
  - `agent_factory.py` - Agent creation and initialization
  - Tests across multiple files
- Existing patterns to follow:
  - Dependency injection through constructors
  - YAML-based configuration
  - structlog for logging
  - Async/await throughout
- Critical compatibility requirements:
  - All existing tests must pass
  - Agent creation APIs unchanged (backward compatible through factory)
  - CLI behavior unchanged
  - No performance degradation
- **GPT-5 API specific requirements:**
  - **Parameter incompatibility**: temperature, top_p, logprobs NOT supported in GPT-5
  - **New parameters**: effort (low/medium/high), reasoning (minimal/balanced/deep)
  - **Intelligent parameter mapping** required to convert old→new parameters
  - **Backward compatibility**: Existing code using temperature must continue working
  - **Validation layer**: Prevent 400 Bad Request errors from invalid parameters
  - **Comprehensive logging**: Log all parameter transformations for debugging
- Package upgrade risks:
  - litellm API may have breaking changes
  - GPT-5 parameter validation must be tested explicitly
  - Verify async patterns still work
  - Test thoroughly before proceeding with refactoring
- Each story must include verification that:
  - Component-specific tests pass
  - Full integration test suite passes
  - Agent execution works correctly with GPT-4 models
  - **GPT-5 parameter adaptation** works correctly
  - Configuration loading successful
  - Parameter mapping produces expected results

The epic should eliminate configuration duplication, enable modern LLM features (GPT-5 with new reasoning parameters), implement intelligent parameter adaptation for API compatibility, improve maintainability through centralization, and maintain system integrity throughout the refactoring process."

## Example LLM Configuration

Here's the proposed `llm_config.yaml` structure:

```yaml
# configs/llm_config.yaml
# Centralized LLM configuration for all agent components

# Default model alias (references models map below)
default_model: "main"

# Model aliases for easy switching
models:
  main: "gpt-4.1"           # Primary model for standard tasks
  fast: "gpt-4.1-mini"       # Fast model for simple tasks
  powerful: "gpt-5"          # Most capable model with reasoning
  legacy: "gpt-4-turbo"      # Fallback option

# Model-specific parameters (overrides default_params for specific models)
model_params:
  # GPT-4 family: Traditional OpenAI parameters
  gpt-4:
    temperature: 0.7
    top_p: 1.0
    max_tokens: 2000
    frequency_penalty: 0.0
    presence_penalty: 0.0
  
  gpt-4.1:
    temperature: 0.7
    top_p: 1.0
    max_tokens: 2000
  
  gpt-4.1-mini:
    temperature: 0.7
    max_tokens: 1500
  
  gpt-4-turbo:
    temperature: 0.7
    top_p: 1.0
    max_tokens: 4000
  
  # GPT-5 family: New reasoning-based parameters
  # IMPORTANT: temperature, top_p, logprobs NOT supported!
  gpt-5:
    effort: "medium"        # Options: low, medium, high
    reasoning: "balanced"   # Options: minimal, balanced, deep
    max_tokens: 4000
    # temperature is FIXED at 1.0 and cannot be changed
  
  gpt-5-mini:
    effort: "low"
    reasoning: "minimal"
    max_tokens: 2000

# Default parameters (fallback for models without specific config)
# NOTE: LLMService will automatically adapt these for GPT-5 models
default_params:
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0
  frequency_penalty: 0.0
  presence_penalty: 0.0

# Retry policy for failed requests
retry_policy:
  max_attempts: 3
  backoff_multiplier: 2     # Exponential backoff (1s, 2s, 4s)
  timeout: 30               # Timeout per request (seconds)
  retry_on_errors:
    - "RateLimitError"
    - "APIConnectionError"
    - "Timeout"
    - "BadRequestError"     # For invalid parameter combinations

# Provider-specific configuration
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
    organization_env: "OPENAI_ORG_ID"  # Optional
    base_url: null  # Use default, or override for Azure/proxies
  
  azure:
    enabled: false
    api_key_env: "AZURE_OPENAI_KEY"
    endpoint_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"

# Logging preferences
logging:
  log_prompts: false        # Don't log full prompts (privacy)
  log_completions: false    # Don't log full completions (privacy)
  log_token_usage: true     # Log token counts
  log_latency: true         # Log request latency
  log_parameter_mapping: true  # Log when parameters are adapted for GPT-5
```

## Migration Path for Existing Code

### Before (Current Pattern):
```python
# agent.py - BEFORE
import litellm

async def compress_history_async(self) -> None:
    response = await litellm.acompletion(
        model="gpt-4.1",  # Hardcoded
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0
    )
```

### After (New Pattern):
```python
# agent.py - AFTER
async def compress_history_async(self) -> None:
    response = await self.llm_service.complete(
        messages=[{"role": "user", "content": summary_prompt}],
        model="main",  # Uses configured model
        temperature=0
    )
```

### Configuration Change Example:
```yaml
# To switch entire system to GPT-5, change ONE line in llm_config.yaml:
models:
  main: "gpt-5"  # Changed from "gpt-4.1"
  # All components now use GPT-5 with automatic parameter adaptation!
```

## Important: GPT-5 API Changes

**Critical information about GPT-5 compatibility:**

OpenAI has significantly changed the API for GPT-5 models. The following parameters are **NO LONGER SUPPORTED**:

❌ **Deprecated Parameters:**
- `temperature` - Fixed at 1.0, cannot be customized
- `top_p` - Not supported for GPT-5
- `logprobs` - Not supported for GPT-5
- `frequency_penalty` - Not applicable to reasoning models
- `presence_penalty` - Not applicable to reasoning models

✅ **New GPT-5 Parameters:**
- `effort` - Controls computation intensity (options: "low", "medium", "high")
- `reasoning` - Controls reasoning depth (options: "minimal", "balanced", "deep")
- `max_tokens` - Still supported (universal parameter)

**What this means for our implementation:**

1. **Automatic Parameter Mapping**: The `LLMService` will automatically detect GPT-5 models and map parameters appropriately
   - When code passes `temperature=0.3`, service converts to `effort="low"`
   - When code passes `temperature=0.7`, service converts to `effort="medium"`
   - Deprecated parameters are filtered out and logged

2. **Model-Specific Configuration**: The `llm_config.yaml` allows defining exact parameters per model
   - GPT-4 models use traditional parameters
   - GPT-5 models use new reasoning parameters
   - No code changes needed to switch between models

3. **Backward Compatibility**: Existing code can continue using `temperature` parameter
   - Service handles conversion transparently
   - Warnings logged when parameters are adapted
   - No breaking changes to existing agent code

4. **Error Prevention**: Service validates parameters before API calls
   - Prevents 400 Bad Request errors from invalid parameter combinations
   - Retries with corrected parameters if needed
   - Comprehensive error messages for debugging

**Practical Example - Automatic Adaptation:**

```python
# Your existing agent code stays the same:
response = await agent.llm_service.complete(
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    model="main",
    temperature=0.3  # Traditional parameter
)

# What happens internally when model="main" resolves to "gpt-5":
# 1. LLMService detects GPT-5 model
# 2. Converts temperature=0.3 → effort="low"
# 3. Removes temperature from API call
# 4. Logs parameter adaptation
# 5. Calls litellm with GPT-5-compatible parameters:
#    {model: "gpt-5", effort: "low", reasoning: "balanced"}

# No code changes needed! Just configure model in llm_config.yaml
```

**References:**
- OpenAI GPT-5 API Documentation: platform.openai.com/docs/guides/latest-model
- Community discussions: community.openai.com/t/temperature-in-gpt-5-models
- LiteLLM GPT-5 support notes
- GitHub issues on parameter compatibility

## Project Analysis Checklist

### Existing Project Context
- ✅ Project purpose and current functionality understood
- ✅ Existing technology stack identified (Python 3.11+, litellm, async/await)
- ✅ Current architecture patterns noted (dependency injection, YAML config)
- ✅ Integration points with existing system identified (Agent, tools, planning, factory)
- ✅ Current pain points documented (scattered config, hardcoded models, old packages)

### Enhancement Scope
- ✅ Enhancement clearly defined and scoped (centralized LLM service)
- ✅ Impact on existing functionality assessed (widespread but backward compatible)
- ✅ Required integration points identified (4 main components + factory)
- ✅ Success criteria established (tests pass, config works, GPT-5 available)
- ✅ Risk mitigation strategies defined (incremental, isolated upgrade, rollback plan)

---

**Epic Created:** 2025-11-11  
**Epic Updated:** 2025-11-11 (Added GPT-5 API compatibility requirements)  
**Epic Status:** Ready for Story Development  
**Estimated Stories:** 6  
**Complexity:** Medium-High (Package upgrade + widespread refactoring + API compatibility layer)  
**Risk Level:** Medium (mitigated through incremental approach + parameter validation)  
**Priority:** High (enables GPT-5, improves maintainability, prevents API errors)  

**Key Technical Challenge:** GPT-5 API parameter changes require intelligent parameter mapping layer to maintain backward compatibility while enabling new reasoning features.

