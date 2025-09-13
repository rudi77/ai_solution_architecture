# Testing Reality

## Current Test Coverage

- **Integration Tests**: `tests/test_api.py` - FastAPI endpoint testing with real OpenAI API
- **End-to-End Tests**: `tests/test_e2e.py` - Full workflow testing with SSE streaming
- **Artifact Tests**: `tests/test_artifacts.py` - Todo list and state artifact generation
- **Manual Testing**: Primary QA method for frontend and agent interactions

## Running Tests

```powershell
# Requires OPENAI_API_KEY for integration tests
uv run pytest -q                    # Run all tests
uv run pytest capstone/tests/ -v    # Verbose test output
```

**Test Dependencies:**
- Real OpenAI API key required (no mocking implemented)
- Tests use actual LLM calls (cost implications)
- Async test framework via pytest-asyncio