# Story 1.1: Azure AI Search SDK Integration and Base Tool Infrastructure

**Epic:** Multimodal RAG Knowledge Retrieval for Agent Framework
**Story ID:** RAG-1.1
**Priority:** High (Foundation - Blocks all other stories)
**Estimate:** 4-6 hours
**Status:** Ready for Development

---

## User Story

**As a** developer maintaining the agent framework,
**I want** to establish the Azure AI Search SDK connection infrastructure,
**so that** all RAG tools can reliably connect to Azure and execute queries with proper authentication and error handling.

---

## Story Context

### Existing System Integration

- **Integrates with:** Existing agent_v2 tool architecture (tool.py base class)
- **Technology:** Python 3.11+, azure-search-documents SDK 11.4+, AsyncIO
- **Follows pattern:** Existing tool initialization pattern (see tools/web_tool.py for reference)
- **Touch points:**
  - requirements.txt (add dependencies)
  - tools/ directory (new base module)
  - Test infrastructure (unit + integration tests)

### Why This Story Matters

This story establishes the **foundation** for all RAG capabilities. It creates the shared infrastructure that all RAG tools will use to connect to Azure AI Search, ensuring:

1. **Consistent authentication** across all tools
2. **Centralized security filtering** via user context
3. **Proper error handling** for Azure SDK exceptions
4. **Reusable patterns** for future RAG tool additions

Without this foundation, each tool would need to duplicate Azure connection logic, leading to inconsistency and maintenance burden.

---

## Acceptance Criteria

### AC1.1.1: AzureSearchBase Class Implementation

**File:** `capstone/agent_v2/tools/azure_search_base.py`

**Requirements:**
- [ ] Create new module `tools/azure_search_base.py`
- [ ] Implement `AzureSearchBase` class with the following:

**Environment Variable Loading:**
```python
class AzureSearchBase:
    """Base class for Azure AI Search integration providing shared connection and security logic."""

    def __init__(self):
        """Initialize Azure Search base configuration from environment variables."""
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.api_key = os.getenv("AZURE_SEARCH_API_KEY")
        self.documents_index = os.getenv("AZURE_SEARCH_DOCUMENTS_INDEX", "documents-metadata")
        self.content_index = os.getenv("AZURE_SEARCH_CONTENT_INDEX", "content-blocks")

        # Validate required environment variables
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure Search configuration missing. Please set:\n"
                "  AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net\n"
                "  AZURE_SEARCH_API_KEY=your-api-key\n"
                "Optional:\n"
                "  AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata (default)\n"
                "  AZURE_SEARCH_CONTENT_INDEX=content-blocks (default)"
            )
```

**SearchClient Factory Method:**
```python
def get_search_client(self, index_name: str) -> SearchClient:
    """
    Create an AsyncSearchClient for the specified index.

    Args:
        index_name: Name of the Azure Search index

    Returns:
        AsyncSearchClient configured with credentials

    Example:
        client = self.get_search_client("content-blocks")
        async with client:
            results = await client.search(...)
    """
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.aio import SearchClient

    return SearchClient(
        endpoint=self.endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(self.api_key)
    )
```

**Async Context Manager Support:**
```python
async def __aenter__(self):
    """Support async context manager pattern."""
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    """Cleanup on context exit."""
    # No cleanup needed for SearchClient (handled per-use)
    pass
```

---

### AC1.1.2: Security Filter Builder

**Method:** `build_security_filter(user_context: Dict) -> str`

**Requirements:**
- [ ] Implement security filter generation method
- [ ] Handle user_context with user_id, department, org_id fields
- [ ] Generate proper OData filter syntax for Azure Search
- [ ] Handle missing/None user_context gracefully (return empty string for testing)

**Implementation:**
```python
def build_security_filter(self, user_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Build OData filter for row-level security based on user context.

    Args:
        user_context: Dict with user_id, department, org_id keys

    Returns:
        OData filter string for access_control_list field

    Examples:
        >>> build_security_filter({"user_id": "u123", "department": "eng"})
        "access_control_list/any(acl: acl eq 'u123' or acl eq 'eng')"

        >>> build_security_filter(None)
        ""
    """
    if not user_context:
        return ""  # No filter for testing scenarios

    filters = []

    if user_context.get("user_id"):
        filters.append(f"acl eq '{user_context['user_id']}'")

    if user_context.get("department"):
        filters.append(f"acl eq '{user_context['department']}'")

    if user_context.get("org_id"):
        filters.append(f"acl eq '{user_context['org_id']}'")

    if not filters:
        return ""

    # Combine with OR logic inside any() predicate
    combined = " or ".join(filters)
    return f"access_control_list/any(acl: {combined})"
```

---

### AC1.1.3: Dependency Management

**File:** `capstone/agent_v2/requirements.txt`

**Requirements:**
- [ ] Add Azure Search Python SDK dependencies
- [ ] Pin versions for stability

**Changes:**
```txt
# Azure AI Search SDK (RAG Enhancement)
azure-search-documents>=11.4.0
azure-core>=1.29.0
```

**Verification:**
```bash
pip install -r requirements.txt
python -c "from azure.search.documents.aio import SearchClient; print('Azure SDK installed successfully')"
```

---

### AC1.1.4: Unit Tests

**File:** `capstone/agent_v2/tests/test_azure_search_base.py`

**Requirements:**
- [ ] Create unit test file
- [ ] Test environment variable validation
- [ ] Test security filter generation
- [ ] Test SearchClient creation

**Test Implementation:**
```python
import pytest
import os
from unittest.mock import patch
from capstone.agent_v2.tools.azure_search_base import AzureSearchBase


class TestAzureSearchBase:
    """Unit tests for AzureSearchBase class."""

    def test_missing_endpoint_raises_error(self):
        """Test that missing AZURE_SEARCH_ENDPOINT raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AzureSearchBase()

            assert "AZURE_SEARCH_ENDPOINT" in str(exc_info.value)
            assert "AZURE_SEARCH_API_KEY" in str(exc_info.value)

    def test_missing_api_key_raises_error(self):
        """Test that missing AZURE_SEARCH_API_KEY raises ValueError."""
        with patch.dict(os.environ, {"AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AzureSearchBase()

            assert "AZURE_SEARCH_API_KEY" in str(exc_info.value)

    def test_valid_config_succeeds(self):
        """Test that valid configuration initializes successfully."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            assert base.endpoint == "https://test.search.windows.net"
            assert base.api_key == "test-key"
            assert base.documents_index == "documents-metadata"  # default
            assert base.content_index == "content-blocks"  # default

    def test_custom_index_names(self):
        """Test that custom index names from env vars are used."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key",
            "AZURE_SEARCH_DOCUMENTS_INDEX": "custom-docs",
            "AZURE_SEARCH_CONTENT_INDEX": "custom-content"
        }):
            base = AzureSearchBase()
            assert base.documents_index == "custom-docs"
            assert base.content_index == "custom-content"

    def test_security_filter_with_full_context(self):
        """Test security filter generation with complete user context."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {
                "user_id": "user123",
                "department": "engineering",
                "org_id": "org456"
            }

            filter_str = base.build_security_filter(user_context)

            assert "access_control_list/any(acl:" in filter_str
            assert "acl eq 'user123'" in filter_str
            assert "acl eq 'engineering'" in filter_str
            assert "acl eq 'org456'" in filter_str
            assert " or " in filter_str

    def test_security_filter_with_partial_context(self):
        """Test security filter with only some fields present."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            user_context = {"user_id": "user123"}

            filter_str = base.build_security_filter(user_context)

            assert "acl eq 'user123'" in filter_str
            assert "engineering" not in filter_str

    def test_security_filter_with_none_context(self):
        """Test that None user_context returns empty filter."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            filter_str = base.build_security_filter(None)

            assert filter_str == ""

    def test_get_search_client_returns_async_client(self):
        """Test that get_search_client returns AsyncSearchClient."""
        with patch.dict(os.environ, {
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key"
        }):
            base = AzureSearchBase()
            client = base.get_search_client("test-index")

            from azure.search.documents.aio import SearchClient
            assert isinstance(client, SearchClient)
```

**Run Tests:**
```bash
pytest capstone/agent_v2/tests/test_azure_search_base.py -v
```

---

### AC1.1.5: Integration Test

**File:** `capstone/agent_v2/tests/integration/test_azure_search_integration.py`

**Requirements:**
- [ ] Create integration test against real Azure instance
- [ ] Verify successful connection
- [ ] Verify basic search query executes

**Test Implementation:**
```python
import pytest
import os
from capstone.agent_v2.tools.azure_search_base import AzureSearchBase


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_search_connection():
    """
    Integration test: Connect to real Azure AI Search and execute basic query.

    Requires environment variables to be set:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_API_KEY
    - AZURE_SEARCH_CONTENT_INDEX (or uses default)
    """
    # Skip if Azure credentials not configured
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    base = AzureSearchBase()

    # Get client for content-blocks index
    client = base.get_search_client(base.content_index)

    # Execute simple search
    async with client:
        results = await client.search(
            search_text="test",
            top=1,
            select=["block_id"]
        )

        # Consume results (just verify no exception)
        result_list = []
        async for result in results:
            result_list.append(result)

        # Don't assert on result count (index might be empty)
        # Just verify the query executed without error
        print(f"Integration test successful. Retrieved {len(result_list)} results.")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_security_filter_applied():
    """Test that security filters are properly applied in real queries."""
    if not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY"):
        pytest.skip("Azure credentials not configured")

    base = AzureSearchBase()
    user_context = {"user_id": "test_user"}
    filter_str = base.build_security_filter(user_context)

    client = base.get_search_client(base.content_index)

    async with client:
        # This should not raise an error even if no results match
        results = await client.search(
            search_text="*",
            filter=filter_str,
            top=1
        )

        async for _ in results:
            pass  # Just verify filter syntax is valid
```

**Run Integration Tests:**
```bash
# Set credentials first
export AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
export AZURE_SEARCH_API_KEY=your-key

# Run integration tests
pytest capstone/agent_v2/tests/integration/test_azure_search_integration.py -v -m integration
```

---

## Integration Verification

### IV1.1.1: No Regression in Existing Agent Tests

**Verification:**
```bash
# Run all existing agent tests
pytest capstone/agent_v2/tests/ -v --ignore=tests/integration

# Expected: All existing tests pass (no failures introduced)
```

**Success Criteria:**
- ✅ All existing unit tests pass
- ✅ No import errors from new module
- ✅ Agent initialization works as before

---

### IV1.1.2: Existing Tools Continue to Function

**Verification:**
```bash
# Test existing web tool
python -c "
from capstone.agent_v2.tools.web_tool import WebSearchTool
tool = WebSearchTool()
print(f'WebSearchTool: {tool.name}')
"

# Test existing file tool
python -c "
from capstone.agent_v2.tools.file_tool import FileReadTool
tool = FileReadTool()
print(f'FileReadTool: {tool.name}')
"
```

**Success Criteria:**
- ✅ All existing tools import successfully
- ✅ Tool instantiation works
- ✅ No dependency conflicts

---

### IV1.1.3: Agent.create_agent() Backward Compatibility

**Verification:**
```python
# Test that existing agent creation still works
from capstone.agent_v2.agent import Agent

agent = Agent.create_agent(
    name="Test Agent",
    description="Test backward compatibility",
    system_prompt=None,
    mission="Test mission",
    work_dir="./test_work",
    llm=None
)

print(f"Agent created: {agent.name}")
print(f"Tool count: {len(agent.tools)}")
```

**Success Criteria:**
- ✅ Agent creates successfully
- ✅ Has all existing tools (8 tools: Web, File, Git, Python, etc.)
- ✅ No errors related to Azure dependencies

---

## Technical Notes

### Integration Approach

**Pattern to Follow:**
Look at `tools/web_tool.py` for reference on how existing tools are structured:
- Class inherits from `Tool` base class
- `__init__` initializes configuration
- `execute()` is async and returns structured dict
- Error handling returns `{"success": False, "error": "..."}`

**AzureSearchBase Differences:**
- This is **not** a Tool itself (it's a base class for tools)
- Provides **shared infrastructure** (connection, security)
- RAG tools will inherit/use this in Story 1.2+

### Key Constraints

1. **Environment Variables Required:**
   - `AZURE_SEARCH_ENDPOINT` - Must be set
   - `AZURE_SEARCH_API_KEY` - Must be set
   - Index names have defaults but can be overridden

2. **Async Pattern:**
   - All Azure SDK operations must use `async with client`
   - Follow existing async/await patterns from agent.py

3. **Error Handling:**
   - Missing env vars → ValueError with clear message
   - Azure SDK errors → Will be handled in individual tools (Story 1.2+)

### File Structure After This Story

```
capstone/agent_v2/
├── tools/
│   ├── azure_search_base.py          # NEW
│   ├── web_tool.py                    # Existing
│   ├── file_tool.py                   # Existing
│   └── ...
├── tests/
│   ├── test_azure_search_base.py      # NEW
│   └── integration/
│       └── test_azure_search_integration.py  # NEW
├── requirements.txt                    # MODIFIED
└── agent.py                            # Unchanged
```

---

## Definition of Done

- [x] **Code Complete:**
  - [ ] `tools/azure_search_base.py` implemented with all methods
  - [ ] requirements.txt updated with Azure SDK dependencies
  - [ ] All methods have docstrings and type hints

- [x] **Tests Pass:**
  - [ ] All unit tests pass (AC1.1.4)
  - [ ] Integration test passes (AC1.1.5)
  - [ ] No regression in existing tests (IV1.1.1, IV1.1.2, IV1.1.3)

- [x] **Quality:**
  - [ ] Code follows PEP 8 (run `black` and `isort`)
  - [ ] Type hints present (run `mypy`)
  - [ ] Structured logging uses structlog pattern
  - [ ] Error messages are clear and actionable

- [x] **Documentation:**
  - [ ] Docstrings explain all public methods
  - [ ] Environment variable setup documented
  - [ ] Integration test instructions clear

---

## Risk Assessment and Mitigation

### Primary Risk: Azure SDK Installation Issues

**Mitigation:**
- Test on clean Python 3.11 environment
- Document exact SDK version requirements
- Provide troubleshooting steps in error messages

**Rollback:**
- This story is purely additive (no modifications to existing code)
- Simply remove new files and dependency lines to rollback

### Compatibility Verification

- [x] **No breaking changes to existing APIs:** ✅ (No existing APIs modified)
- [x] **No database changes:** ✅ (No database involved)
- [x] **Follows existing design patterns:** ✅ (Follows tool.py pattern)
- [x] **Performance impact negligible:** ✅ (Only loads when RAG tools used)

---

## Dependencies

**Depends on:** None (Foundation story)

**Blocks:**
- Story 1.2: Semantic Search Tool
- Story 1.3: Document Metadata Tools
- All subsequent RAG stories

---

## Implementation Checklist

### Phase 1: Setup (30 min)
- [ ] Create `tools/azure_search_base.py` file
- [ ] Update `requirements.txt`
- [ ] Install dependencies: `pip install -r requirements.txt`

### Phase 2: Core Implementation (2 hours)
- [ ] Implement `AzureSearchBase.__init__()` with env var loading
- [ ] Implement `get_search_client()` method
- [ ] Implement `build_security_filter()` method
- [ ] Add async context manager support

### Phase 3: Testing (2 hours)
- [ ] Create `tests/test_azure_search_base.py`
- [ ] Implement all unit tests (AC1.1.4)
- [ ] Create `tests/integration/test_azure_search_integration.py`
- [ ] Run unit tests locally
- [ ] Run integration test against Azure (if credentials available)

### Phase 4: Verification (1 hour)
- [ ] Run existing agent tests (IV1.1.1)
- [ ] Verify existing tools work (IV1.1.2)
- [ ] Test Agent.create_agent() (IV1.1.3)
- [ ] Code quality checks (black, isort, mypy)

### Phase 5: Documentation (30 min)
- [ ] Add inline comments for complex logic
- [ ] Verify all docstrings present
- [ ] Update any README if needed

---

**Ready for development! 🚀**

*This story establishes the foundation for all RAG functionality. Take care to ensure the base infrastructure is solid - all future stories depend on this.*
