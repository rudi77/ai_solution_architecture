# 2. Requirements

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
