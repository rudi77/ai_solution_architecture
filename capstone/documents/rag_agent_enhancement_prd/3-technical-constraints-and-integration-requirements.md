# 3. Technical Constraints and Integration Requirements

### 3.1 Existing Technology Stack

| Category | Current Technology | Version | Usage in Enhancement | Notes |
|----------|-------------------|---------|---------------------|-------|
| Runtime | Python | 3.11+ | Core platform | Maintain as primary runtime |
| HTTP Client | aiohttp | 3.9+ | Existing tools only | Not used for Azure integration |
| LLM Integration | litellm | 1.7.7.0 | RAG system prompt execution | Existing in Agent class |
| State Management | pickle + aiofiles | Built-in + 23.2.1 | RAG session state | No changes required |
| Logging | structlog | 24.2.0 | RAG tool logging | Extend existing usage |
| Async Runtime | asyncio | Built-in | All RAG tools async | Maintain existing patterns |

### 3.2 New Technology Requirements

| Technology | Version | Purpose | Rationale | Integration Method |
|------------|---------|---------|-----------|-------------------|
| **azure-search-documents** | **11.4+** | **Azure AI Search SDK** | **Official Python SDK with async support, type safety, automatic retry logic** | **New dependency, AsyncSearchClient for queries** |
| azure-core | 1.29+ | Azure SDK core (dependency) | Required by azure-search-documents | Auto-installed with SDK |

**Dependency Management:**
```txt
# requirements.txt additions:
azure-search-documents>=11.4.0
azure-core>=1.29.0
```

### 3.3 Integration Approach

**Azure AI Search Integration Strategy:**
- Use **azure-search-documents SDK** instead of REST API
- Instantiate `AsyncSearchClient` with async support in each RAG tool
- Leverage SDK features:
  - Automatic retry logic for transient failures
  - Type-safe query builders (`SearchQuery`, `VectorizedQuery`)
  - Built-in authentication via `AzureKeyCredential`
  - Native async/await support with `AsyncSearchClient`

**Code Integration Pattern:**
```python
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient

# In RAG tool __init__:
self.search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name="content-blocks",
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
)

# In async execute method:
async with self.search_client:
    results = await self.search_client.search(
        search_text=query,
        top=top_k,
        filter=odata_filter,
        select=["block_id", "content", "image_url", "page_number"]
    )
```

**Database Integration Strategy:**
- **No database changes required** - Azure AI Search acts as external search service
- State remains pickle-based per existing StateManager
- RAG-specific state (user_context, search_history) stored in state dict under `rag.*` namespace

**Testing Integration Strategy:**
- Unit tests with mocked `AsyncSearchClient` responses (pytest-mock)
- Integration tests against real Azure AI Search test index
- SDK provides built-in test utilities
- Follow existing test patterns from architecture.md requirements

### 3.4 Code Organization and Standards

**File Structure Approach:**
```
capstone/agent_v2/
├── tools/
│   ├── rag_semantic_search_tool.py      # NEW: SemanticSearchTool
│   ├── rag_list_documents_tool.py       # NEW: ListDocumentsTool
│   ├── rag_get_document_tool.py         # NEW: GetDocumentTool
│   ├── rag_metadata_search_tool.py      # NEW: SearchMetadataTool (optional)
│   └── [existing tools unchanged]
├── prompts/                              # NEW: System prompts directory
│   ├── __init__.py                       # NEW
│   ├── generic_system_prompt.py         # MOVED: Existing prompt
│   └── rag_system_prompt.py             # NEW: RAG-specific prompt
├── agent.py                              # MODIFIED: Add create_rag_agent()
├── requirements.txt                      # MODIFIED: Add azure-search-documents
└── [all other files unchanged]
```

**Naming Conventions:**
- RAG tools prefixed with `rag_` for clear identification
- Follow existing snake_case convention (rag_semantic_search_tool.py)
- Class names: `SemanticSearchTool`, `ListDocumentsTool` (PascalCase per existing tools)

**Coding Standards:**
- PEP 8 compliance (existing standard)
- Type hints throughout (matching agent.py patterns)
- Use `AsyncSearchClient` for async/await compatibility
- Structured logging with contextual fields
- Proper async context manager usage (`async with self.search_client`)

**Documentation Standards:**
- Docstrings for all classes and methods (Google style per existing code)
- Inline comments for Azure SDK-specific patterns
- README update with RAG usage examples and Azure SDK setup

### 3.5 Deployment and Operations

**Build Process Integration:**
- Add `azure-search-documents` to requirements.txt
- Update installation docs: `pip install -r requirements.txt`
- Environment variable validation at agent startup
- Document Azure configuration in README

**Deployment Strategy:**
- Same as existing: Direct Python execution or Docker (per architecture.md)
- Environment variables loaded via os.getenv() or python-dotenv
- Azure SDK credentials via environment variables (no config files)

**Monitoring and Logging:**
Extend existing structlog usage with RAG-specific fields:
- `azure_operation` - SDK operation name (e.g., "search", "get_document")
- `search_latency_ms` - Search performance tracking
- `result_count` - Number of results returned
- `index_name` - Which index was queried
- `filter_applied` - OData filter for security tracking

**Configuration Management:**
Environment variables:
```bash
# Required
AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
AZURE_SEARCH_API_KEY=<your-key>

# Optional (with defaults)
AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata
AZURE_SEARCH_CONTENT_INDEX=content-blocks
```

### 3.6 Risk Assessment and Mitigation

**Technical Risks:**

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| Azure SDK version incompatibility | High - tool failures | Low | Pin SDK version in requirements.txt, test with specified version |
| Azure AI Search query failures | High - no results returned | Medium | SDK provides automatic retry (3 attempts), implement fallback error messages |
| Image SAS URL expiration | Medium - broken images | Low | Document 1-hour validity, consider URL refresh logic in future |
| Large result sets causing latency | Medium - slow responses | Medium | Implement `top` parameter limits (default 10), SDK handles pagination |
| System prompt quality issues | High - poor planning | High | Iterative prompt engineering, include examples in prompt, user testing |
| Async context manager lifecycle | Medium - resource leaks | Low | Use `async with` pattern consistently, document proper usage |

**Integration Risks:**

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| Breaking existing agent functionality | Critical | Low | Comprehensive regression tests, optional RAG tools, system prompt as parameter |
| SDK dependency conflicts | Medium - installation issues | Low | Use virtual environments, test on clean Python 3.11+ install |
| State serialization issues with RAG context | Medium | Low | Store only serializable data (strings, dicts), avoid SDK objects in state |
| Tool registration conflicts | Low | Very Low | Unique tool names (`rag_semantic_search` vs `web_search`) |

**Deployment Risks:**

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| Missing environment variables | High - startup failure | Medium | Validate at init, clear error messages, env var template in README |
| Azure credential exposure | Critical | Low | Use environment variables, never commit .env files, document security practices |
| Network connectivity to Azure | High - tool failures | Low | SDK handles retries, graceful degradation, timeout handling, clear error messages |
| SDK authentication failures | High - no access | Medium | Validate credentials at tool init, provide clear error with setup instructions |

**Mitigation Strategies Summary:**
- **Backward Compatibility**: RAG tools are additive, existing agent works without them
- **Testing**: 80%+ coverage requirement, integration tests against live Azure with SDK
- **Error Handling**: SDK provides rich exception types, catch and convert to agent-friendly error format
- **Security**: Environment variables for credentials, access_control_list enforcement in queries via SDK filter parameter
- **Performance**: Async I/O throughout with AsyncSearchClient, configurable timeouts, result limits
- **SDK Benefits**: Automatic retries, type safety, better error messages than raw REST API

---
