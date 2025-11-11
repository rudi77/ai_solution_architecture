# Testing Reality

### Current Test Structure

**Test Directories**:
- `tests/` - Core agent tests (in agent_v2 root)
- `tests/integration/` - Integration tests (RAG, synthesis)
- `cli/tests/` - CLI unit tests

**Known Tests**:
- RAG synthesis: `tests/integration/test_rag_synthesis.py` (mentioned in README)
- CLI tests: Files exist in `cli/tests/` directory

**Running Tests**:
```powershell
# CLI tests
uv run -m pytest .\cli\tests -q

# Core tests (from repo root)
.\.venv\Scripts\python.exe -m pytest tests -q

# Integration tests
pytest tests/integration/ -v -k rag
```

### Test Coverage

**Unknown Areas**:
- Overall coverage percentage not documented
- Unit test completeness unclear
- Integration test scope unknown beyond RAG

**Best Practice** (from project guidelines):
- Tests required for all functions/modules
- Separate tests/ directory (✅ implemented)
- Targeted exception handling (presumably tested)

---
