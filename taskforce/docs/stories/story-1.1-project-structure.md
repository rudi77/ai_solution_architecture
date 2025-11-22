# Story 1.1: Establish Taskforce Project Structure and Dependencies

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.1  
**Status**: Pending  
**Priority**: Critical  
**Estimated Points**: 2  
**Dependencies**: None (Foundation story)

---

## User Story

As a **developer**,  
I want **the Taskforce project structure created with proper Python packaging**,  
so that **I have a clean foundation for implementing Clean Architecture layers**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/` directory at repository root (sibling to `capstone/`)
2. ✅ Create `taskforce/pyproject.toml` with project metadata, dependencies (LiteLLM, Typer, FastAPI, structlog, SQLAlchemy, Alembic, pytest), and CLI entry points
3. ✅ Create `taskforce/src/taskforce/` with subdirectories: `core/`, `infrastructure/`, `application/`, `api/`
4. ✅ Create subdirectory structure:
   - `core/domain/`, `core/interfaces/`, `core/prompts/`
   - `infrastructure/persistence/`, `infrastructure/llm/`, `infrastructure/tools/`, `infrastructure/memory/`
   - `application/` (factory, executor, profiles modules)
   - `api/routes/`, `api/cli/`
5. ✅ Create `taskforce/tests/` with `unit/`, `integration/`, `fixtures/` subdirectories
6. ✅ Create placeholder `__init__.py` files in all packages
7. ✅ Verify `uv sync` successfully installs all dependencies
8. ✅ Create `taskforce/README.md` with project overview and setup instructions

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 in `capstone/agent_v2` continues to function independently (no import conflicts)
- **IV2: Integration Point Verification** - `uv sync` in `taskforce/` completes successfully with all dependencies resolved
- **IV3: Performance Impact Verification** - N/A (project setup only)

---

## Technical Notes

**Directory Structure to Create:**
```
taskforce/
├── pyproject.toml
├── README.md
├── src/
│   └── taskforce/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── domain/
│       │   │   └── __init__.py
│       │   ├── interfaces/
│       │   │   └── __init__.py
│       │   └── prompts/
│       │       └── __init__.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── persistence/
│       │   │   └── __init__.py
│       │   ├── llm/
│       │   │   └── __init__.py
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   ├── native/
│       │   │   │   └── __init__.py
│       │   │   ├── rag/
│       │   │   │   └── __init__.py
│       │   │   └── mcp/
│       │   │       └── __init__.py
│       │   └── memory/
│       │       └── __init__.py
│       ├── application/
│       │   └── __init__.py
│       └── api/
│           ├── __init__.py
│           ├── routes/
│           │   └── __init__.py
│           └── cli/
│               └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── __init__.py
│   ├── integration/
│   │   └── __init__.py
│   └── fixtures/
│       └── __init__.py
└── docs/
    └── stories/
```

**Key Dependencies (pyproject.toml):**
- Python = "^3.11"
- litellm = "^1.7.7"
- typer = "^0.9.0"
- fastapi = "^0.116.1"
- structlog = "^24.2.0"
- sqlalchemy = "^2.0"
- alembic = "^1.13"
- pytest = "^8.4.2"
- pytest-asyncio = "^0.23"
- rich = "^13.0.0"
- pydantic = "^2.0"
- pydantic-settings = "^2.0"
- aiofiles = "^23.2.1"

---

## Definition of Done

- [ ] All directories and `__init__.py` files created
- [ ] `pyproject.toml` contains all required dependencies
- [ ] `uv sync` completes without errors
- [ ] `README.md` provides clear setup instructions
- [ ] Agent V2 (`capstone/agent_v2`) still works independently
- [ ] Code committed to version control

