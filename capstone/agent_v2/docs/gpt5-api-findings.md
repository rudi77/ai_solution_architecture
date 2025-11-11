# GPT-5 API Findings

**Date:** 2025-11-11  
**LiteLLM Version:** 1.50.0+  
**OpenAI SDK Version:** 1.50.0+  

## Summary

This document captures the exact behavior of GPT-5 API parameter handling after upgrading to latest litellm and openai packages.

## Traditional Parameters

| Parameter | Behavior | Notes |
|-----------|----------|-------|
| temperature | [To be tested] | Run validation script to determine |
| top_p | [To be tested] | Run validation script to determine |
| logprobs | [To be tested] | Run validation script to determine |
| frequency_penalty | [To be tested] | Not tested in validation script |
| presence_penalty | [To be tested] | Not tested in validation script |

## New GPT-5 Parameters

| Parameter | Values | Behavior | Notes |
|-----------|--------|----------|-------|
| effort | low, medium, high | [To be tested] | Run validation script to determine |
| reasoning | minimal, balanced, deep | [To be tested] | Run validation script to determine |

## Backward Compatibility

- GPT-4 models: [To be tested]
- Traditional parameters with GPT-4: [To be tested]
- Async patterns: [To be tested]

## Validation Instructions

To populate this document with actual findings, run the validation script:

```powershell
# Set your API key
$env:OPENAI_API_KEY = "your-api-key-here"

# Run validation script
python -m capstone.agent_v2.tests.manual.test_gpt5_params
```

The script will test:
1. Traditional parameter rejection (temperature, top_p)
2. New GPT-5 parameters (effort, reasoning)
3. Combined parameter usage
4. Backward compatibility with GPT-4

## Recommendations

Based on findings (to be completed after validation):

1. [Recommendation based on findings]
2. [...]

## Example Code

```python
# Working example for GPT-5 (to be updated after validation)
response = await litellm.acompletion(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello"}],
    effort="medium",
    reasoning="balanced",
    max_tokens=50
)
```

## Notes

- This document should be updated after running the validation script
- Requires actual GPT-5 API access to complete validation
- All findings should be based on actual test results, not assumptions

