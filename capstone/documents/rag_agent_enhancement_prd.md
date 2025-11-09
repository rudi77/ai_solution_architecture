# Agent Framework RAG Enhancement PRD

**Product Requirements Document**
**Version:** 1.0
**Date:** 2025-11-09
**Author:** John (PM Agent)
**Project:** Multimodal RAG Knowledge Retrieval for Agent_v2 Framework

---

## 1. Intro Project Analysis and Context

### 1.1 Analysis Source

- **Source:** User-provided technical design document + IDE-based analysis of existing agent_v2 codebase
- **Mode:** Document-based requirements analysis combined with actual implementation review

### 1.2 Current Project State

**Existing System:**
The project has a production-ready **ReAct agent framework** (agent_v2) with autonomous planning and execution capabilities:

**Core Components:**
- `Agent` class (agent.py:291-888) - ReAct orchestrator with Thought→Action→Observation cycle
- `TodoListManager` (planning/todolist.py) - Autonomous planning with outcome-oriented TodoItems
- `StateManager` (statemanager.py) - Async pickle-based state persistence
- `MessageHistory` class - Context-aware conversation management with LLM-based compression
- **8 existing tools**: WebSearch, WebFetch, Python, GitHub, Git, FileRead, FileWrite, PowerShell

**Key Architecture Patterns:**
- Async/await throughout (AsyncIterator for event streaming)
- Event-driven architecture (AgentEvent types: THOUGHT, ACTION, TOOL_RESULT, ASK_USER, COMPLETE, ERROR)
- Deterministic planning with acceptance criteria (outcome-oriented, not tool-specific)
- Retry mechanism with max_attempts per TodoItem
- Structured logging with structlog
- Tool-based architecture with base Tool class providing common interface

**Current Capabilities:**
- Generic agent orchestration using ReAct pattern
- Task planning and decomposition via TodoListManager
- State management for conversation context
- Tool execution framework with 8 general-purpose tools
- Async event streaming for real-time execution monitoring

**Current Limitations (RAG-relevant):**
- No semantic search or retrieval capabilities
- No integration with vector databases or search services
- Tools are file/web/code focused, not knowledge-retrieval focused
- System prompt is generic - no domain-specific intelligence injection
- No multimodal content handling (images, diagrams)

### 1.3 Available Documentation Analysis

✓ **Tech Stack Documentation** - Python 3.11+, AsyncIO, litellm, structlog
✓ **Architecture Documentation** - Comprehensive architecture.md exists (docs/architecture.md)
✓ **API Documentation** - Tool interfaces documented in code
✓ **Technical Design** - Agentic RAG technical design document provided
✗ **Coding Standards** - Implicit via code (PEP 8, type hints, async patterns)
✗ **UX/UI Guidelines** - Not applicable (agent-only scope)
✓ **Existing PRD** - Rich CLI Tool PRD exists (docs/prd.md)

### 1.4 Enhancement Scope Definition

**Enhancement Type:**
✓ **New Feature Addition** + **Integration with New Systems**

**Enhancement Description:**
This enhancement adds specialized RAG (Retrieval-Augmented Generation) capabilities to the existing generic ReAct agent framework. The agent will gain the ability to perform autonomous multimodal knowledge search across enterprise documents by integrating with Azure AI Search. The enhancement introduces a RAG-specific system prompt that injects domain intelligence into the generic agent, plus a suite of specialized tools for semantic search, document listing, and metadata filtering.

**Impact Assessment:**
✓ **Moderate to Significant Impact**
- **Moderate:** Core agent logic (ReAct, TodoList, State Manager) remains unchanged
- **Significant:** New tool layer, new system prompt architecture, integration with external Azure services
- **Additive:** All changes are additions, no modifications to existing core logic

### 1.5 Goals and Background Context

#### Goals

- Enable the existing agent framework to perform autonomous, multimodal knowledge retrieval from enterprise documents
- Integrate Azure AI Search for semantic search across text and image content blocks
- Implement intelligent query classification and planning for RAG tasks (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, COMPARISON)
- Maintain strict separation between generic agent logic and RAG-specific skills (inject via system prompt and tools)
- Support proactive clarification for ambiguous queries (e.g., "which report?" when multiple matches exist)
- Provide source tracking and citation for all retrieved information
- Deliver multimodal responses with embedded images and diagrams directly in markdown format
- Preserve 100% backward compatibility with existing agent functionality

#### Background Context

**Problem:**
Enterprise knowledge is locked in dense, hard-to-search documents (manuals, reports, PDFs). Standard RAG systems are reactive and provide only text snippets, forcing users to open source documents for full context - especially diagrams and images.

**Vision:**
Transform the robust generic ReAct agent framework into a **proactive knowledge assistant** by injecting RAG-specific intelligence through a specialized system prompt and tool suite. The system goal is to provide a multimodal user experience so comprehensive that it eliminates the need to consult original source documents.

**Solution:**
This PRD describes the enhancement of the existing agent_v2 framework with RAG capabilities. The innovation lies in three areas:

1. **Multimodal Indexing:** Text and images are treated as semantically searchable "content blocks" in Azure AI Search
2. **Intelligent Synthesis:** The agent embeds relevant images directly in context within textual answers using markdown format
3. **Agent Intelligence:** RAG logic is not hard-coded but injected into the generic agent via a specialized system prompt

**Key Architectural Principle:**
The core agent logic (ReAct, State Management, Planning) remains generic. RAG capabilities are implemented as a "skill set" (Tools + System Prompt), enabling reusability of the agent framework for other tasks.

### 1.6 Change Log

| Change | Date | Version | Description | Author |
|--------|------|---------|-------------|---------|
| Initial PRD | 2025-11-09 | 1.0 | Agent-only brownfield PRD created from technical design document and agent_v2 codebase analysis | John (PM Agent) |

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: RAG-Specific System Prompt Injection**
The Agent class shall accept a RAG-specific system prompt as a parameter that **completely replaces** the GENERIC_SYSTEM_PROMPT. This RAG prompt shall contain:
- Query classification instructions (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON)
- Planning patterns for knowledge retrieval workflows
- Multimodal response formatting guidelines (markdown with embedded images)
- Source citation requirements
- Clarification guidelines for ambiguous queries

**FR2: Multimodal Content Block Search**
The system shall provide a `SemanticSearchTool` that performs hybrid semantic + keyword search across the Azure AI Search `content-blocks` index, returning both text chunks and image blocks with their associated metadata (block_type, page_number, image_url, image_caption, doc_id, filename).

**FR3: Document Metadata Operations**
The system shall provide a `ListDocumentsTool` and `GetDocumentTool` that query the Azure AI Search `documents-metadata` index for:
- Document listing with filtering by metadata (upload_date, document_type, department)
- Retrieval of pre-computed summaries (summary_brief, summary_standard)
- Document details by doc_id

**FR4: Query Classification and Autonomous Planning**
The TodoListManager shall interpret RAG-specific missions and generate plans that:
- Classify queries into types (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON)
- Create appropriate search → synthesis workflows
- Include proactive clarification questions for ambiguous queries (e.g., "which report?" when multiple matches exist)
- Generate outcome-oriented acceptance criteria per existing TodoItem pattern

**FR5: Multimodal Response Synthesis**
The system shall use the **existing PythonTool** for synthesis. A synthesis step in the TodoList shall execute Python code that:
- Takes retrieved content blocks as context parameter
- Combines text and image URLs into markdown format
- Embeds images using `![caption](url)` syntax
- Formats citations in "(Source: filename.pdf, S. X)" format
- Returns the final markdown response

**FR6: Source Tracking and Citation**
All retrieved content blocks shall include complete provenance metadata (doc_id, filename, page_number, block_type), and final responses shall cite sources in the format: "(Source: filename.pdf, S. X)" after each fact or image.

**FR7: Security and Access Control**
All RAG tools shall:
- Accept user context (user_id, department, org_id) from the Agent
- Automatically inject OData filter expressions into Azure AI Search queries
- Enforce row-level security via access_control_list field in both indexes
- Handle missing user_context gracefully (empty filter for testing scenarios)

**FR8: Clarification Before Execution**
When a document-specific query is ambiguous (e.g., "summarize the report" matches 3 documents), the TodoListManager shall:
- Generate an `ask_user` action with numbered options listing matched documents
- Wait for user selection before creating the execution plan
- Resume execution with clarified context

**FR9: Tool Discovery and Registration**
New RAG tools shall:
- Integrate via a factory method `Agent.create_rag_agent()` that instantiates all RAG tools
- Load Azure configuration from environment variables (AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY)
- Be registered alongside existing tools without modifying core Agent logic
- Follow the existing Tool base class interface pattern

**FR10: Backward Compatibility**
The enhanced agent shall:
- Maintain full compatibility with existing `Agent.create_agent()` method
- Preserve all existing tools, missions, and state persistence
- Keep RAG capabilities opt-in via `create_rag_agent()` factory method
- Not modify any existing core agent classes (Agent, StateManager, TodoListManager)

---

### 2.2 Non-Functional Requirements

**NFR1: Response Latency**
Semantic search operations shall return results within 2 seconds for queries against indexes containing up to 100,000 content blocks (Azure AI Search performance target).

**NFR2: Azure AI Search Integration**
All search operations shall use the **Azure Search Python SDK (azure-search-documents v11.4+)** with:
- `AsyncSearchClient` for async query execution
- `AzureKeyCredential` for API key authentication
- SDK automatic retry logic (3 attempts with exponential backoff)
- Proper async context manager usage (`async with`)
- Error handling for SDK exceptions (`HttpResponseError`, `ServiceRequestError`)
- Timeout configuration (30s max per query)

**NFR3: Existing Performance Preservation**
RAG tool additions shall not impact existing agent performance:
- Startup time for non-RAG missions shall remain under 500ms (existing baseline)
- RAG agent initialization shall complete in <1 second
- Memory footprint increase shall be <50MB for Azure SDK

**NFR4: State Compatibility**
RAG-enhanced sessions shall:
- Use the existing pickle-based StateManager without schema changes
- Store RAG-specific state in the existing state dict under namespaced keys (e.g., `rag.user_context`)
- Maintain backward compatibility with existing state files

**NFR5: Async Execution**
All RAG tools shall:
- Follow the existing async/await pattern
- Yield AgentEvents during long-running operations (TOOL_STARTED, TOOL_RESULT)
- Use AsyncSearchClient from Azure SDK for consistent streaming UX
- Not block the event loop

**NFR6: Logging and Observability**
RAG tools shall use existing structlog patterns with structured fields:
- `azure_operation` - SDK operation name (e.g., "search", "get_document")
- `search_query` - User query string
- `result_count` - Number of results returned
- `index_name` - Which Azure index was queried
- `search_latency_ms` - Search performance tracking
- `filter_applied` - OData filter for security audit

**NFR7: Error Handling**
RAG tools shall return structured error observations matching the existing pattern:
```python
{
    "success": False,
    "error": "message",
    "type": "ErrorType",
    "hints": ["suggestion1", "suggestion2"]
}
```
This enables the agent's existing retry logic to function correctly.

**NFR8: Multimodal Content Handling**
Image URLs returned in search results shall:
- Be Azure Blob Storage SAS URLs with at least 1-hour validity
- Not be downloaded/processed by the agent (only embedded in markdown)
- Include image_caption for accessibility and context

**NFR9: Configuration Management**
Azure AI Search connection details shall be loaded from environment variables:
- `AZURE_SEARCH_ENDPOINT` - Search service endpoint (required)
- `AZURE_SEARCH_API_KEY` - API key for authentication (required)
- `AZURE_SEARCH_DOCUMENTS_INDEX` - Name of documents-metadata index (default: "documents-metadata")
- `AZURE_SEARCH_CONTENT_INDEX` - Name of content-blocks index (default: "content-blocks")

RAG tools shall validate these at initialization using SDK's `SearchClient` constructor and raise `ValueError` with clear setup instructions if missing or invalid.

**NFR10: Testing Requirements**
RAG tools shall include:
- Unit tests with mocked Azure SDK responses achieving 80%+ code coverage
- Integration tests against a test Azure AI Search instance
- Regression tests ensuring existing agent functionality unchanged
- End-to-end workflow tests (search → synthesize → complete)

---

### 2.3 Compatibility Requirements

**CR1: Agent Execution Interface Compatibility**
The existing `Agent.execute(user_message, session_id)` method signature shall remain unchanged. RAG missions shall be passed as standard mission strings, with RAG-specific behavior activated by system prompt content.

**CR2: Tool Base Class Compatibility**
All RAG tools shall:
- Inherit from the existing `Tool` base class (tool.py)
- Implement the standard interface: `name`, `description`, `parameters_schema`, `function_tool_schema`, and `async execute(**kwargs)` method
- Follow the same patterns as existing tools (WebSearchTool, FileReadTool, etc.)

**CR3: StateManager Compatibility**
RAG-enhanced agents shall:
- Continue using the existing pickle-based state persistence
- Not require changes to StateManager class
- Store RAG context in standard state dict format (nested under "rag" key)

**CR4: TodoList Schema Compatibility**
RAG-generated plans shall:
- Use the existing TodoItem structure (position, description, acceptance_criteria, dependencies, status)
- Not modify the TodoItem dataclass schema
- Follow outcome-oriented descriptions per existing patterns

**CR5: Event Streaming Compatibility**
RAG tools shall:
- Emit the existing AgentEvent types (TOOL_STARTED, TOOL_RESULT, ASK_USER, COMPLETE)
- Not introduce new event types
- Ensure compatibility with existing event consumers

---

## 3. Technical Constraints and Integration Requirements

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

## 4. Epic and Story Structure

### 4.1 Epic Approach

**Epic Structure Decision:** Single comprehensive epic

**Rationale:**
This RAG enhancement represents a **cohesive feature addition** to the existing agent framework. All components work together to deliver multimodal knowledge retrieval - the tools, system prompt, and synthesis capability are interdependent. Splitting into multiple epics would create artificial boundaries and complicate integration testing.

- All RAG tools share common infrastructure (Azure SDK, authentication, user context)
- System prompt governs behavior of all tools coordinately
- Testing requires all components working together (can't test synthesis without search results)
- User value is delivered only when complete workflow functions (search → retrieve → synthesize)
- Based on existing agent architecture analysis, this is a **moderate impact enhancement** (new tools + prompt, core agent unchanged)

---

## 4.2 Epic 1: Multimodal RAG Knowledge Retrieval for Agent Framework

**Epic Goal:**
Extend the existing agent_v2 ReAct framework with Azure AI Search-powered multimodal knowledge retrieval capabilities, enabling autonomous search across text and images with intelligent synthesis of markdown responses including embedded visuals and source citations.

**Integration Requirements:**
- Maintain full backward compatibility with existing Agent.execute() interface
- Preserve all existing tools (WebSearch, FileTool, PythonTool, etc.) functionality
- Use existing StateManager, TodoListManager, and MessageHistory without modifications
- Follow existing async/await patterns and AgentEvent streaming architecture
- Integrate Azure Search Python SDK alongside existing tool patterns

---

### Story 1.1: Azure AI Search SDK Integration and Base Tool Infrastructure

**As a** developer maintaining the agent framework,
**I want** to establish the Azure AI Search SDK connection infrastructure,
**so that** all RAG tools can reliably connect to Azure and execute queries with proper authentication and error handling.

#### Acceptance Criteria

**AC1.1.1:** A new module `tools/azure_search_base.py` exists containing an `AzureSearchBase` class that:
- Loads environment variables (AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, index names)
- Validates required variables and raises `ValueError` with clear instructions if missing
- Provides `get_search_client(index_name: str) -> AsyncSearchClient` method
- Implements proper async context manager pattern

**AC1.1.2:** The `AzureSearchBase` class includes a method `build_security_filter(user_context: Dict) -> str` that:
- Accepts user_context with user_id, department, org_id
- Returns OData filter string: `access_control_list/any(acl: acl eq 'user_id' or acl eq 'department')`
- Handles missing user_context gracefully (returns empty filter for testing)

**AC1.1.3:** requirements.txt includes:
```
azure-search-documents>=11.4.0
azure-core>=1.29.0
```

**AC1.1.4:** Unit tests exist for `AzureSearchBase`:
- Test environment variable validation (missing ENDPOINT raises ValueError)
- Test security filter generation with various user_context inputs
- Test SearchClient creation returns AsyncSearchClient instance

**AC1.1.5:** Integration test connects to real Azure AI Search endpoint using test credentials and successfully executes a basic search query

#### Integration Verification

- **IV1.1.1:** All existing agent tests pass without modification (no regression)
- **IV1.1.2:** Existing tools (WebSearchTool, FileReadTool) continue to function normally
- **IV1.1.3:** Agent.create_agent() works without RAG tools (backward compatibility preserved)

---

### Story 1.2: Semantic Search Tool for Content Blocks

**As a** RAG-enabled agent,
**I want** to search across multimodal content blocks (text and images) semantically,
**so that** I can retrieve relevant information including diagrams and visualizations for user queries.

#### Acceptance Criteria

**AC1.2.1:** A new tool `SemanticSearchTool` exists in `tools/rag_semantic_search_tool.py` that:
- Inherits from `Tool` base class (tool.py)
- Implements `name = "rag_semantic_search"`
- Provides `description` explaining multimodal search capability
- Defines `parameters_schema` with: query (str, required), top_k (int, default=10), filters (dict, optional)

**AC1.2.2:** The `execute(**kwargs)` async method:
- Accepts: query, top_k, filters, user_context
- Uses `AsyncSearchClient` to search the content-blocks index
- Applies security filter from user_context via `build_security_filter()`
- Returns structured result:
```python
{
  "success": True,
  "results": [
    {
      "block_id": "...",
      "block_type": "text|image",
      "content": "..." (if text),
      "image_url": "..." (if image),
      "image_caption": "..." (if image),
      "doc_id": "...",
      "filename": "...",
      "page_number": 5,
      "score": 0.85
    }
  ],
  "result_count": 10
}
```

**AC1.2.3:** Error handling:
- Azure SDK exceptions caught and returned as `{"success": False, "error": "...", "type": "AzureSearchError", "hints": [...]}`
- Network timeouts (30s) handled gracefully
- Empty results return `{"success": True, "results": [], "result_count": 0}`

**AC1.2.4:** Structured logging with structlog:
- Logs: `azure_operation="search"`, `search_query`, `result_count`, `index_name="content-blocks"`, `search_latency_ms`

**AC1.2.5:** Unit tests with mocked AsyncSearchClient verify:
- Successful search returns properly formatted results
- Empty results handled correctly
- Azure exceptions converted to agent error format
- Security filter correctly applied

**AC1.2.6:** Integration test against real Azure index retrieves actual content blocks

#### Integration Verification

- **IV1.2.1:** Tool can be registered in Agent.create_agent() tools list without errors
- **IV1.2.2:** Agent can execute a TodoItem that calls rag_semantic_search and receives results
- **IV1.2.3:** Existing agent performance unaffected (non-RAG missions execute in same time)

---

### Story 1.3: Document Metadata Tools (List and Get)

**As a** RAG-enabled agent,
**I want** to list available documents and retrieve document summaries,
**so that** I can answer queries about document availability and provide pre-computed summaries without full-text search.

#### Acceptance Criteria

**AC1.3.1:** A new tool `ListDocumentsTool` exists in `tools/rag_list_documents_tool.py` that:
- Inherits from `Tool` base class
- Implements `name = "rag_list_documents"`
- Parameters: filters (dict, optional), sort_by (str, default="upload_date"), limit (int, default=20), user_context
- Searches the `documents-metadata` index
- Returns: `{"success": True, "documents": [{"doc_id", "filename", "title", "document_type", "upload_date", "summary_brief"}], "count": N}`

**AC1.3.2:** A new tool `GetDocumentTool` exists in `tools/rag_get_document_tool.py` that:
- Implements `name = "rag_get_document"`
- Parameters: doc_id (str, required), user_context
- Uses AsyncSearchClient to retrieve single document by doc_id
- Returns: `{"success": True, "document": {"doc_id", "filename", "title", "summary_standard", "page_count", ...}}`

**AC1.3.3:** Both tools apply security filter from user_context

**AC1.3.4:** Error handling for document not found, access denied, Azure errors

**AC1.3.5:** Unit tests for both tools with mocked Azure responses

**AC1.3.6:** Integration tests retrieve actual documents from Azure index

#### Integration Verification

- **IV1.3.1:** Both tools register successfully in Agent.create_agent()
- **IV1.3.2:** Agent can execute TodoItems calling these tools
- **IV1.3.3:** Tools work alongside rag_semantic_search without conflicts

---

### Story 1.4: RAG System Prompt for Query Classification and Planning

**As a** product manager defining agent behavior,
**I want** a comprehensive RAG-specific system prompt,
**so that** the agent intelligently classifies queries and generates optimal plans for knowledge retrieval tasks.

#### Acceptance Criteria

**AC1.4.1:** A new file `prompts/rag_system_prompt.py` exists containing `RAG_SYSTEM_PROMPT` string that includes:
- **Query Classification Section**: Instructions to classify queries as LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON
- **Planning Patterns Section**: Examples of typical TodoList structures for each query type
- **Clarification Guidelines**: When to ask for user input (ambiguous document references, missing filters)
- **Tool Usage Rules**: When to use rag_semantic_search vs rag_list_documents vs rag_get_document
- **Synthesis Instructions**: How to combine text and image blocks into markdown with citations
- **Source Citation Format**: Requirement to cite as "(Source: filename.pdf, S. X)"

**AC1.4.2:** The prompt includes **concrete examples** for each query type:
```
Example - CONTENT_SEARCH:
User: "How does the XYZ pump work?"
Plan:
1. Search for content about XYZ pump functionality (acceptance: ≥3 relevant blocks retrieved)
2. Synthesize results into markdown response (acceptance: Response includes text + images + citations)
```

**AC1.4.3:** The prompt specifies **multimodal response format**:
- Embed images using `![caption](url)` markdown syntax
- Include source after each fact: "(Source: manual.pdf, S. 12)"
- Prioritize showing diagrams when available

**AC1.4.4:** The prompt is **parameterizable** - accepts variables like available_tools list, user_context details

**AC1.4.5:** Documentation in prompts/README.md explains:
- How to use the RAG prompt vs GENERIC_SYSTEM_PROMPT
- How to customize for specific domains
- Query classification logic

**AC1.4.6:** Unit test verifies prompt structure (contains required sections, valid Python string)

#### Integration Verification

- **IV1.4.1:** Agent initialized with RAG_SYSTEM_PROMPT successfully replaces GENERIC_SYSTEM_PROMPT
- **IV1.4.2:** TodoListManager generates RAG-appropriate plans when using RAG prompt
- **IV1.4.3:** Existing GENERIC_SYSTEM_PROMPT still works for non-RAG missions (no breaking changes)

---

### Story 1.5: Multimodal Synthesis via PythonTool

**As a** RAG-enabled agent,
**I want** to synthesize retrieved content blocks into cohesive markdown responses,
**so that** users receive complete answers with embedded images and proper citations without opening source documents.

#### Acceptance Criteria

**AC1.5.1:** The RAG system prompt (from Story 1.4) includes a **synthesis step template** that instructs the agent to:
- Use the existing `PythonTool` (tools/code_tool.py)
- Pass retrieved content blocks via the `context` parameter
- Execute Python code that formats markdown

**AC1.5.2:** A reference synthesis script is documented in `docs/rag_synthesis_example.py`:
```python
# Example synthesis code that agent would generate
def synthesize_response(blocks, query):
    markdown = f"# Answer to: {query}\n\n"
    for block in blocks:
        if block['block_type'] == 'text':
            markdown += f"{block['content']}\n\n"
            markdown += f"*(Source: {block['filename']}, S. {block['page_number']})*\n\n"
        elif block['block_type'] == 'image':
            markdown += f"![{block['image_caption']}]({block['image_url']})\n\n"
            markdown += f"*(Source: {block['filename']}, S. {block['page_number']})*\n\n"
    return markdown
```

**AC1.5.3:** The RAG system prompt instructs the agent to:
- Generate synthesis code dynamically based on retrieved results
- Handle mixed text/image blocks appropriately
- Ensure all sources are cited
- Return the final markdown string

**AC1.5.4:** Integration test demonstrates:
- Agent receives RAG mission: "Explain the XYZ process"
- TodoList includes: Step 1 (search), Step 2 (synthesize with PythonTool)
- Final response contains both text and embedded image markdown
- All content includes source citations

**AC1.5.5:** The synthesis approach leverages **existing PythonTool context parameter** (no new tool needed)

#### Integration Verification

- **IV1.5.1:** Existing PythonTool (tools/code_tool.py) works without modification for synthesis
- **IV1.5.2:** Agent successfully executes synthesis step using PythonTool
- **IV1.5.3:** Final markdown output is valid and renders correctly in markdown viewers

---

### Story 1.6: RAG Agent Factory Method and End-to-End Integration

**As a** developer using the agent framework,
**I want** a simple factory method to create a RAG-enabled agent,
**so that** I can quickly instantiate an agent with all RAG tools and the appropriate system prompt without manual configuration.

#### Acceptance Criteria

**AC1.6.1:** A new static method exists in `agent.py`:
```python
@staticmethod
def create_rag_agent(
    name: str,
    description: str,
    mission: str,
    work_dir: str,
    llm,
    user_context: Optional[Dict] = None
) -> "Agent"
```

**AC1.6.2:** The method:
- Loads Azure configuration from environment variables (validates at startup)
- Instantiates all RAG tools: SemanticSearchTool, ListDocumentsTool, GetDocumentTool
- Includes all existing tools (Web, File, Git, Python, etc.)
- Sets system_prompt to RAG_SYSTEM_PROMPT (from prompts/rag_system_prompt.py)
- Passes user_context to all RAG tools
- Creates TodoListManager and StateManager per existing pattern
- Returns fully configured Agent instance

**AC1.6.3:** Example usage documented in README:
```python
from capstone.agent_v2.agent import Agent

agent = Agent.create_rag_agent(
    name="RAG Assistant",
    description="Multimodal knowledge retrieval agent",
    mission="Explain how the safety valve works",
    work_dir="./rag_sessions",
    llm=None,
    user_context={"user_id": "user123", "department": "engineering"}
)

async for event in agent.execute(user_message="Start", session_id="session-1"):
    if event.type == AgentEventType.COMPLETE:
        print(event.data["todolist"])
```

**AC1.6.4:** Integration test demonstrates full RAG workflow:
- Create RAG agent using factory method
- Execute mission: "What are the main risks in Project Titan from Q3 reports?"
- Agent classifies as CONTENT_SEARCH
- TodoList includes: search → synthesize steps
- Agent calls rag_semantic_search with proper filters
- Agent calls PythonTool for synthesis
- Final response includes text + images + citations
- All events stream correctly (THOUGHT, TOOL_RESULT, COMPLETE)

**AC1.6.5:** Backward compatibility test:
- Existing `Agent.create_agent()` method unchanged
- Non-RAG agents continue to work identically
- Both factory methods can coexist

**AC1.6.6:** Error scenarios handled:
- Missing Azure environment variables → Clear error message with setup instructions
- Invalid credentials → Azure SDK error caught and reported
- Empty search results → Agent handles gracefully (returns "No results found")

#### Integration Verification

- **IV1.6.1:** All existing agent tests pass (no regressions from adding RAG tools)
- **IV1.6.2:** RAG agent can execute both RAG missions and generic missions (tool flexibility)
- **IV1.6.3:** StateManager persists RAG session state correctly (backward compatible)
- **IV1.6.4:** Performance: RAG agent initialization completes in <1 second
- **IV1.6.5:** Security: User context properly enforced in all Azure queries

---

## 5. Story Sequencing and Dependencies

### 5.1 Critical Story Sequence

This story sequence minimizes risk to the existing agent system:

1. **Story 1.1 (Base Infrastructure)**: Establishes Azure SDK connection in isolation - no agent modifications yet
2. **Story 1.2 (First Tool)**: Adds one tool following existing Tool pattern - validates integration approach
3. **Story 1.3 (Additional Tools)**: Scales proven pattern to remaining tools
4. **Story 1.4 (System Prompt)**: Pure additive - doesn't modify existing prompts
5. **Story 1.5 (Synthesis)**: Leverages existing PythonTool - no new code execution logic
6. **Story 1.6 (Integration)**: Ties everything together - only story that touches agent.py

### 5.2 Dependencies

- Story 1.2 **depends on** 1.1 (needs base infrastructure)
- Story 1.3 **depends on** 1.2 (follows proven tool pattern)
- Story 1.5 **depends on** 1.2 (needs search results to synthesize)
- Story 1.6 **depends on** ALL previous stories (integrates everything)

### 5.3 Rollback Points

- After each story, existing agent functionality remains intact
- RAG features are opt-in via `create_rag_agent()` - never affects `create_agent()`
- Can deploy stories 1.1-1.5 without 1.6 (tools exist but not used)

---

## 6. Success Metrics

### 6.1 Primary Metric (UX)

**Click-Through-Rate Reduction:**
Reduction in the rate at which users open source documents after receiving agent responses. Target: 70% reduction (users open source documents only 30% of the time vs. 100% baseline).

### 6.2 Secondary Metrics (Quality)

**Answer Quality Rating:**
User-rated answer quality (5-point scale). Target: Average rating ≥4.0.

**Multimodal Response Rate:**
Percentage of responses that include both text and relevant images. Target: ≥60% for queries where images exist in index.

**Citation Accuracy:**
Percentage of responses with complete and correct source citations. Target: 100%.

### 6.3 Agent Efficiency Metrics

**Plan Completion Rate:**
Rate of successfully completed TodoLists without human intervention. Target: ≥80%.

**Clarification Rate:**
How often the agent asks for user clarification. Target: <20% (indicates good query understanding).

**Tool Success Rate:**
Percentage of RAG tool executions that succeed. Target: ≥95%.

### 6.4 Performance Metrics

**Search Latency:**
Average time for semantic search to return results. Target: <2 seconds.

**End-to-End Response Time:**
Time from mission start to COMPLETE event. Target: <10 seconds for typical queries.

**Agent Overhead:**
RAG agent initialization time vs. standard agent. Target: <500ms difference.

---

## 7. Appendices

### 7.1 Azure AI Search Index Schemas

#### Content Blocks Index (`content-blocks`)

| Field | Type | Description |
|-------|------|-------------|
| block_id | String (key) | Unique identifier |
| doc_id | String | Parent document reference |
| page_number | Int | Source page |
| block_type | String | "text" or "image" |
| content | String | Text content (if text block) |
| content_vector | Collection(Single) | Embedding for text |
| image_url | String | Blob Storage URL (if image block) |
| image_caption | String | AI-generated caption (if image) |
| image_caption_vector | Collection(Single) | Embedding for caption |
| access_control_list | Collection(String) | Security: user_ids, departments |

#### Documents Metadata Index (`documents-metadata`)

| Field | Type | Description |
|-------|------|-------------|
| doc_id | String (key) | Unique identifier |
| filename | String | Original filename |
| title | String | Extracted title |
| document_type | String | "Manual", "Report", etc. |
| upload_date | DateTimeOffset | Upload timestamp |
| author | String | Document author |
| department | String | Owning department |
| page_count | Int | Number of pages |
| summary_brief | String | Short summary (2-3 sentences) |
| summary_standard | String | Full summary (1-2 paragraphs) |
| access_control_list | Collection(String) | Security: user_ids, departments |

### 7.2 Environment Variable Template

```bash
# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
AZURE_SEARCH_API_KEY=<your-api-key>

# Index Names (optional, defaults provided)
AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata
AZURE_SEARCH_CONTENT_INDEX=content-blocks

# User Context (example for testing)
RAG_USER_ID=user123
RAG_DEPARTMENT=engineering
RAG_ORG_ID=org456
```

### 7.3 Glossary

- **RAG**: Retrieval-Augmented Generation - AI pattern combining search with LLM generation
- **Content Block**: A single unit of content (text chunk or image) in the search index
- **Multimodal**: Supporting both text and images
- **Semantic Search**: Search based on meaning rather than exact keyword matching
- **OData Filter**: Query syntax for filtering Azure Search results
- **SAS URL**: Shared Access Signature URL for secure Azure Blob access
- **ReAct**: Reasoning + Acting agent pattern (Thought → Action → Observation)
- **TodoList**: The agent's deterministic execution plan
- **Acceptance Criteria**: Observable conditions that define when a TodoItem is complete

---

**End of PRD**

*Generated with assistance from Claude Code*
*Co-Authored-By: Claude <noreply@anthropic.com>*
