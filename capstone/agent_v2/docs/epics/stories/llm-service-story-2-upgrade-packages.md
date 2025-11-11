# Story 2: Upgrade LiteLLM and OpenAI Packages

**Epic:** LLM Service Consolidation & Modernization  
**Story ID:** LLM-SERVICE-002  
**Status:** Ready for Development  
**Priority:** High (Blocker for GPT-5 support)  
**Estimated Effort:** 2-3 days  

## Story Description

Upgrade `litellm` and `openai` packages to latest versions that support GPT-5 models and new API features. Validate GPT-5 parameter behavior and ensure backward compatibility with existing async patterns.

## User Story

**As a** developer  
**I want** to upgrade to the latest LiteLLM and OpenAI packages  
**So that** GPT-5 models are available and new reasoning parameters (effort, reasoning) can be used

## Acceptance Criteria

### Functional Requirements

1. **Package Upgrades**
   - [x] Update `pyproject.toml`:
     - `litellm>=1.50.0` (or latest stable with GPT-5 support)
     - `openai>=1.50.0` (or latest stable compatible with litellm)
   - [x] Run `uv sync` to update `uv.lock`
   - [x] Verify no dependency conflicts

2. **Compatibility Verification**
   - [x] All existing tests pass after upgrade
   - [x] Async patterns work unchanged (`await litellm.acompletion()`)
   - [x] No breaking changes in LiteLLM API
   - [x] structlog integration still works

3. **GPT-5 API Validation**
   - [x] Create validation script: `test_gpt5_params.py`
   - [x] Verify GPT-5 model is available in litellm
   - [x] Test traditional parameters behavior:
     - Confirm `temperature` causes error or is silently ignored
     - Confirm `top_p` not supported
     - Confirm `logprobs` not supported
   - [x] Test new GPT-5 parameters work:
     - `effort` parameter accepted (values: low, medium, high)
     - `reasoning` parameter accepted (values: minimal, balanced, deep)
     - `max_tokens` still supported
   - [x] Document exact behavior in findings

4. **Documentation**
   - [x] Document exact package versions used
   - [x] Document GPT-5 parameter behavior findings
   - [x] Document any API changes discovered
   - [x] Update migration notes if needed

### Non-Functional Requirements

- [x] No performance degradation
- [x] Backward compatibility maintained
- [x] All async operations remain stable

## Technical Details

### Package Version Research

**LiteLLM Latest Versions:**
- Research latest stable release supporting GPT-5
- Check changelog for breaking changes
- Verify async support maintained

**OpenAI SDK Latest Versions:**
- Must be compatible with chosen litellm version
- Check for GPT-5 API support
- Verify async client unchanged

### Update pyproject.toml

```toml
[project]
name = "hybrid-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "aiohttp>=3.9",
    "fastapi>=0.116.1",
    "openai>=1.50.0",  # UPDATED for GPT-5 support
    "PyYAML>=6.0",
    "toml>=0.10",
    "uvicorn[standard]>=0.35.0",
    "aiofiles==23.2.1",
    "structlog==24.2.0",
    "litellm>=1.50.0",  # UPDATED for GPT-5 support
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "setuptools>=65.0.0",
    "azure-search-documents>=11.4.0",
    "azure-core>=1.29.0",
]

[dependency-groups]
dev = [
    "pytest>=8.4.2",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
]
```

### GPT-5 Validation Script

Create `capstone/agent_v2/tests/manual/test_gpt5_params.py`:

```python
"""
Manual test script to validate GPT-5 API parameter behavior.

Run this script manually to verify GPT-5 parameter handling:
    python -m capstone.agent_v2.tests.manual.test_gpt5_params

Requirements:
- OPENAI_API_KEY environment variable set
- Latest litellm and openai packages installed
- Access to GPT-5 models
"""

import asyncio
import os
import sys
from typing import Dict, Any
import litellm


class GPT5ParameterValidator:
    """Validator for GPT-5 API parameter behavior."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            print("❌ OPENAI_API_KEY not set")
            sys.exit(1)
    
    async def test_traditional_temperature(self) -> Dict[str, Any]:
        """Test if temperature parameter is accepted for GPT-5."""
        print("\n🧪 Test 1: GPT-5 with temperature parameter")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                temperature=0.5,
                max_tokens=10
            )
            
            result = {
                "status": "accepted",
                "warning": "Temperature was accepted (unexpected for GPT-5)",
                "response": response.choices[0].message.content[:50]
            }
            print(f"   ⚠️  Temperature parameter ACCEPTED (unexpected)")
            print(f"   Response: {result['response']}")
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            result = {
                "status": "rejected",
                "error_type": error_type,
                "error_message": error_msg[:200]
            }
            
            if "temperature" in error_msg.lower() or "parameter" in error_msg.lower():
                print(f"   ✓ Temperature parameter REJECTED (expected)")
                print(f"   Error: {error_type}")
            else:
                print(f"   ❓ Unexpected error: {error_type}")
                print(f"   Message: {error_msg[:100]}")
        
        return result
    
    async def test_traditional_top_p(self) -> Dict[str, Any]:
        """Test if top_p parameter is accepted for GPT-5."""
        print("\n🧪 Test 2: GPT-5 with top_p parameter")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                top_p=0.9,
                max_tokens=10
            )
            
            result = {
                "status": "accepted",
                "warning": "top_p was accepted (unexpected for GPT-5)"
            }
            print(f"   ⚠️  top_p parameter ACCEPTED (unexpected)")
            
        except Exception as e:
            result = {
                "status": "rejected",
                "error_type": type(e).__name__,
                "error_message": str(e)[:200]
            }
            print(f"   ✓ top_p parameter REJECTED (expected)")
        
        return result
    
    async def test_gpt5_effort_parameter(self) -> Dict[str, Any]:
        """Test if effort parameter works for GPT-5."""
        print("\n🧪 Test 3: GPT-5 with effort parameter")
        
        results = {}
        for effort_level in ["low", "medium", "high"]:
            try:
                response = await litellm.acompletion(
                    model="gpt-5",
                    messages=[{"role": "user", "content": "Say 'hello' once."}],
                    effort=effort_level,
                    max_tokens=10
                )
                
                results[effort_level] = {
                    "status": "success",
                    "response": response.choices[0].message.content[:30]
                }
                print(f"   ✓ effort='{effort_level}' WORKS")
                
            except Exception as e:
                results[effort_level] = {
                    "status": "failed",
                    "error": str(e)[:100]
                }
                print(f"   ❌ effort='{effort_level}' FAILED: {type(e).__name__}")
        
        return results
    
    async def test_gpt5_reasoning_parameter(self) -> Dict[str, Any]:
        """Test if reasoning parameter works for GPT-5."""
        print("\n🧪 Test 4: GPT-5 with reasoning parameter")
        
        results = {}
        for reasoning_level in ["minimal", "balanced", "deep"]:
            try:
                response = await litellm.acompletion(
                    model="gpt-5",
                    messages=[{"role": "user", "content": "Say 'hello' once."}],
                    reasoning=reasoning_level,
                    max_tokens=10
                )
                
                results[reasoning_level] = {
                    "status": "success",
                    "response": response.choices[0].message.content[:30]
                }
                print(f"   ✓ reasoning='{reasoning_level}' WORKS")
                
            except Exception as e:
                results[reasoning_level] = {
                    "status": "failed",
                    "error": str(e)[:100]
                }
                print(f"   ❌ reasoning='{reasoning_level}' FAILED: {type(e).__name__}")
        
        return results
    
    async def test_combined_gpt5_params(self) -> Dict[str, Any]:
        """Test GPT-5 with combined effort + reasoning parameters."""
        print("\n🧪 Test 5: GPT-5 with effort + reasoning combined")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Explain quantum entanglement in one sentence."}],
                effort="medium",
                reasoning="balanced",
                max_tokens=50
            )
            
            result = {
                "status": "success",
                "response": response.choices[0].message.content
            }
            print(f"   ✓ Combined parameters WORK")
            print(f"   Response: {result['response'][:100]}")
            
        except Exception as e:
            result = {
                "status": "failed",
                "error_type": type(e).__name__,
                "error": str(e)[:200]
            }
            print(f"   ❌ Combined parameters FAILED: {type(e).__name__}")
        
        return result
    
    async def test_gpt4_still_works(self) -> Dict[str, Any]:
        """Verify GPT-4 models still work with traditional parameters."""
        print("\n🧪 Test 6: GPT-4.1 with traditional parameters (baseline)")
        
        try:
            response = await litellm.acompletion(
                model="gpt-4.1",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                temperature=0.7,
                max_tokens=10
            )
            
            result = {
                "status": "success",
                "response": response.choices[0].message.content
            }
            print(f"   ✓ GPT-4.1 with temperature WORKS (baseline confirmed)")
            
        except Exception as e:
            result = {
                "status": "failed",
                "error": str(e)[:200]
            }
            print(f"   ❌ GPT-4.1 FAILED (unexpected!): {type(e).__name__}")
        
        return result
    
    async def run_all_tests(self):
        """Run all validation tests."""
        print("=" * 60)
        print("GPT-5 Parameter Validation Suite")
        print("=" * 60)
        
        self.results["test_1_temperature"] = await self.test_traditional_temperature()
        self.results["test_2_top_p"] = await self.test_traditional_top_p()
        self.results["test_3_effort"] = await self.test_gpt5_effort_parameter()
        self.results["test_4_reasoning"] = await self.test_gpt5_reasoning_parameter()
        self.results["test_5_combined"] = await self.test_combined_gpt5_params()
        self.results["test_6_gpt4_baseline"] = await self.test_gpt4_still_works()
        
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        
        # Summarize findings
        print("\n📋 Findings:")
        print("1. Traditional parameters (temperature, top_p):")
        if self.results["test_1_temperature"]["status"] == "rejected":
            print("   ✓ Correctly rejected for GPT-5")
        else:
            print("   ⚠️  Unexpectedly accepted (may be silently ignored)")
        
        print("\n2. New GPT-5 parameters:")
        effort_results = self.results["test_3_effort"]
        if all(r["status"] == "success" for r in effort_results.values()):
            print("   ✓ 'effort' parameter fully supported")
        
        reasoning_results = self.results["test_4_reasoning"]
        if all(r["status"] == "success" for r in reasoning_results.values()):
            print("   ✓ 'reasoning' parameter fully supported")
        
        print("\n3. Backward compatibility:")
        if self.results["test_6_gpt4_baseline"]["status"] == "success":
            print("   ✓ GPT-4 with traditional parameters still works")
        
        return self.results


async def main():
    """Main entry point."""
    validator = GPT5ParameterValidator()
    results = await validator.run_all_tests()
    
    # Exit with appropriate code
    failures = sum(
        1 for test_name, result in results.items()
        if isinstance(result, dict) and result.get("status") == "failed"
    )
    
    print(f"\n{'✓' if failures == 0 else '❌'} Tests completed with {failures} failures")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
```

## Files to Modify

1. `capstone/agent_v2/pyproject.toml` - Update package versions
2. `capstone/agent_v2/uv.lock` - Regenerated by uv sync

## Files to Create

1. `capstone/agent_v2/tests/manual/test_gpt5_params.py` - Validation script
2. `capstone/agent_v2/tests/manual/__init__.py` - Package init
3. `capstone/agent_v2/docs/gpt5-api-findings.md` - Document findings

## Testing Requirements

### Pre-Upgrade Tests

```powershell
# Run all tests before upgrade
cd capstone/agent_v2
pytest tests/ -v

# Document baseline results
pytest tests/ --cov=capstone.agent_v2 --cov-report=term
```

### Upgrade Process

```powershell
# Step 1: Update pyproject.toml (edit file manually)

# Step 2: Sync dependencies
uv sync

# Step 3: Verify installation
uv pip list | Select-String -Pattern "litellm|openai"

# Step 4: Run tests immediately
pytest tests/ -v
```

### GPT-5 Validation

```powershell
# Set API key
$env:OPENAI_API_KEY = "your-key-here"

# Run validation script
python -m capstone.agent_v2.tests.manual.test_gpt5_params

# Review findings
cat capstone/agent_v2/docs/gpt5-api-findings.md
```

### Post-Upgrade Verification

```python
# tests/test_package_upgrades.py
import pytest
import litellm
import openai


def test_litellm_version():
    """Verify litellm version is upgraded."""
    import litellm
    version = litellm.__version__
    major, minor = map(int, version.split('.')[:2])
    assert major >= 1 and minor >= 50, f"litellm version too old: {version}"


def test_openai_version():
    """Verify openai version is upgraded."""
    import openai
    version = openai.__version__
    major, minor = map(int, version.split('.')[:2])
    assert major >= 1 and minor >= 50, f"openai version too old: {version}"


@pytest.mark.asyncio
async def test_litellm_async_still_works():
    """Verify litellm async patterns unchanged."""
    # This should not raise ImportError or AttributeError
    assert hasattr(litellm, 'acompletion')
    assert callable(litellm.acompletion)
```

## Validation Checklist

- [ ] `pyproject.toml` updated with new versions
- [ ] `uv sync` executed successfully
- [ ] No dependency conflicts reported
- [ ] All existing tests pass (pytest)
- [ ] GPT-5 validation script created
- [ ] Validation script runs successfully
- [ ] GPT-5 parameter behavior documented
- [ ] Findings documented in `gpt5-api-findings.md`
- [ ] Backward compatibility verified (GPT-4 still works)
- [ ] Async patterns unchanged
- [ ] No performance degradation

## Documentation Required

### GPT-5 API Findings Document

Create `capstone/agent_v2/docs/gpt5-api-findings.md`:

```markdown
# GPT-5 API Findings

**Date:** YYYY-MM-DD  
**LiteLLM Version:** X.X.X  
**OpenAI SDK Version:** X.X.X  

## Summary

Document the exact behavior of GPT-5 API parameter handling.

## Traditional Parameters

| Parameter | Behavior | Notes |
|-----------|----------|-------|
| temperature | [rejected/ignored/accepted] | Error message if rejected |
| top_p | [rejected/ignored/accepted] | |
| logprobs | [rejected/ignored/accepted] | |
| frequency_penalty | [rejected/ignored/accepted] | |
| presence_penalty | [rejected/ignored/accepted] | |

## New GPT-5 Parameters

| Parameter | Values | Behavior | Notes |
|-----------|--------|----------|-------|
| effort | low, medium, high | [works/fails] | |
| reasoning | minimal, balanced, deep | [works/fails] | |

## Backward Compatibility

- GPT-4 models: [✓ working / ❌ broken]
- Traditional parameters with GPT-4: [✓ working / ❌ broken]
- Async patterns: [✓ unchanged / ❌ changed]

## Recommendations

1. [Recommendation based on findings]
2. [...]

## Example Code

```python
# Working example for GPT-5
response = await litellm.acompletion(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello"}],
    effort="medium",
    reasoning="balanced"
)
```
```

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking API changes | High | Test thoroughly, document all changes |
| GPT-5 not available | High | Verify model access, document requirements |
| Dependency conflicts | Medium | Use uv to resolve, pin versions if needed |
| Test failures after upgrade | High | Have rollback plan, fix issues before proceeding |

## Rollback Plan

If critical issues found:

```powershell
# Revert pyproject.toml changes
git checkout HEAD -- capstone/agent_v2/pyproject.toml

# Restore old dependencies
uv sync

# Verify rollback
pytest tests/ -v
```

## Definition of Done

- [x] Packages upgraded successfully
- [x] All existing tests pass
- [x] GPT-5 validation script created and runs
- [x] Parameter behavior documented
- [x] No dependency conflicts
- [x] Backward compatibility confirmed
- [x] Team notified of changes
- [x] Documentation updated

## Next Steps

After this story:
1. ✅ GPT-5 support verified
2. → Story 3: Refactor Agent class to use LLMService (can proceed)
3. → Story 4-6: Refactor other components

---

**Story Created:** 2025-11-11  
**Last Updated:** 2025-11-11  
**Assigned To:** TBD  
**Reviewer:** TBD

