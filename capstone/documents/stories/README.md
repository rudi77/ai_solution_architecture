# RAG Agent Enhancement - Story Implementation Documents

This directory contains detailed implementation documents for all user stories in the **Multimodal RAG Knowledge Retrieval for Agent Framework** epic.

---

## Story Overview

| Story | Title | Priority | Estimate | Status | Dependencies |
|-------|-------|----------|----------|--------|--------------|
| **1.1** | Azure AI Search SDK Integration and Base Tool Infrastructure | High | 4-6 hours | ✅ **Ready** | None |
| **1.2** | Semantic Search Tool for Content Blocks | High | 6-8 hours | Pending | 1.1 |
| **1.3** | Document Metadata Tools (List and Get) | Medium | 4-6 hours | ✅ **Done** | 1.1, 1.2 |
| **1.3.1** | Generic LLM Tool for Response Generation | High | 3-4 hours | ✅ **Ready** | None |
| **1.4** | RAG System Prompt for Query Classification and Planning | High | 6-8 hours | ✅ **Ready** | 1.3.1 |
| **1.5** | Multimodal Synthesis via PythonTool | Medium | 4-5 hours | ✅ **Ready** | 1.2, 1.4 |
| **1.6** | RAG Agent Factory Method and End-to-End Integration | High | 6-8 hours | ✅ **Ready** | All (1.1-1.5) |

**Total Estimate:** 33-45 hours (~1 week for solo developer, ~4-5 days for pair)

**Stories with Complete Documents:** 6 of 7 (86% complete) ✅

---

## Implementation Sequence

### Phase 1: Foundation (Stories 1.1 + 1.4)
**Duration:** 10-14 hours (2 days)

These can be developed **in parallel** as they don't depend on each other:

1. **Story 1.1** - Azure SDK base infrastructure
2. **Story 1.4** - RAG system prompt

**Deliverables:**
- ✅ Azure connection established
- ✅ Security filtering ready
- ✅ RAG intelligence defined in prompt

---

### Phase 2: Tools (Stories 1.2 + 1.3)
**Duration:** 10-14 hours (2 days)

**Sequential development** (1.2 must complete before 1.3):

3. **Story 1.2** - Semantic search tool (validates base infrastructure)
4. **Story 1.3** - Document metadata tools (follows proven pattern from 1.2)

**Deliverables:**
- ✅ All RAG tools implemented
- ✅ Search across text + images working
- ✅ Document listing/retrieval working

---

### Phase 3: Synthesis (Story 1.5)
**Duration:** 4-5 hours (1 day)

5. **Story 1.5** - Synthesis via PythonTool

**Deliverables:**
- ✅ Multimodal markdown generation working
- ✅ Citation formatting correct

---

### Phase 4: Integration (Story 1.6)
**Duration:** 6-8 hours (1 day)

6. **Story 1.6** - Factory method + end-to-end testing

**Deliverables:**
- ✅ `Agent.create_rag_agent()` method
- ✅ Full workflow tested
- ✅ All integration tests passing

---

## Story Documents

### ✅ Story 1.1: Azure AI Search SDK Integration and Base Tool Infrastructure
**File:** [`story-1-1-azure-search-sdk-base-infrastructure.md`](./story-1-1-azure-search-sdk-base-infrastructure.md)

**What it delivers:**
- `tools/azure_search_base.py` - Base class for Azure Search integration
- Environment variable configuration
- Security filter builder for user context
- Unit + integration tests

**Key Files Created:**
- `capstone/agent_v2/tools/azure_search_base.py`
- `capstone/agent_v2/tests/test_azure_search_base.py`
- `capstone/agent_v2/tests/integration/test_azure_search_integration.py`

**Dependencies Added:**
```
azure-search-documents>=11.4.0
azure-core>=1.29.0
```

---

### 📋 Story 1.2: Semantic Search Tool for Content Blocks
**File:** `story-1-2-semantic-search-tool.md` (to be created)

**What it delivers:**
- `SemanticSearchTool` class - Search across multimodal content blocks
- Hybrid search (text + images) using Azure AI Search
- Structured result formatting with block_type, image_url, citations
- Error handling for Azure SDK exceptions

**Key Files:**
- `capstone/agent_v2/tools/rag_semantic_search_tool.py`
- `capstone/agent_v2/tests/test_rag_semantic_search_tool.py`

**Tool Interface:**
```python
tool.execute(
    query="How does the XYZ pump work?",
    top_k=10,
    filters={},
    user_context={"user_id": "user123", "department": "engineering"}
)
# Returns: {"success": True, "results": [...], "result_count": 10}
```

---

### ✅ Story 1.3: Document Metadata Tools (List and Get)
**File:** [`story-1.3-document-metadata-tools.md`](./story-1.3-document-metadata-tools.md)

**What it delivers:**
- `ListDocumentsTool` - List documents with filters and sorting
- `GetDocumentTool` - Retrieve single document with summary
- Both tools query `content-blocks` index (using faceting/aggregation)
- Security filtering applied automatically
- Fallback mechanism when faceting not available

**Key Files:**
- `capstone/agent_v2/tools/rag_list_documents_tool.py`
- `capstone/agent_v2/tools/rag_get_document_tool.py`
- `capstone/agent_v2/tests/test_rag_document_tools.py`
- `capstone/agent_v2/tests/integration/test_rag_document_tools_integration.py`

**Tool Interfaces:**
```python
# List documents
list_tool.execute(
    filters={"document_type": "Manual"},
    limit=20,
    user_context={...}
)

# Get specific document
get_tool.execute(
    document_id="doc-12345",
    user_context={...}
)
```

**Status:** ✅ Implemented, tested, QA approved

---

### ✅ Story 1.3.1: Generic LLM Tool for Response Generation
**File:** [`story-1.3.1-generic-llm-tool.md`](./story-1.3.1-generic-llm-tool.md)

**What it delivers:**
- `LLMTool` - Generic tool for LLM text generation
- Enables agents to formulate natural language responses as tool actions
- Supports context injection (pass structured data for synthesis)
- Works for all agents (RAG, Git, File, etc.) - not RAG-specific
- Privacy-safe logging (metadata only, no full prompts/responses)

**Key Files:**
- `capstone/agent_v2/tools/llm_tool.py`
- `capstone/agent_v2/tests/test_llm_tool.py`
- `capstone/agent_v2/tests/integration/test_llm_tool_integration.py`

**Tool Interface:**
```python
# Formulate response to user
llm_tool.execute(
    prompt="Based on the retrieved documents, answer: 'Which documents are available?'",
    context={
        "documents": [
            {"title": "doc1.pdf", "chunks": 214},
            {"title": "doc2.pdf", "chunks": 15}
        ]
    },
    max_tokens=500,
    temperature=0.7
)
# Returns: {"success": True, "generated_text": "...", "tokens_used": 234}
```

**Why This Tool?**
- Solves the "agent retrieves data but doesn't respond to user" problem
- Makes text generation an explicit, visible workflow step
- Enables both interactive (chat) and autonomous (workflow) modes
- Reusable for summaries, translations, formatting, etc.

**Status:** ✅ Story document created, ready for implementation

---

### ✅ Story 1.4: RAG System Prompt for Query Classification and Planning
**File:** [`story-1.4-rag-system-prompt.md`](./story-1.4-rag-system-prompt.md)

**What it delivers:**
- `prompts/rag_system_prompt.py` - Complete RAG intelligence defining agent behavior
- Query classification into 5 categories (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON)
- Planning patterns for each query type with complete TodoList examples
- Tool usage rules (when to use rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
- **Response generation guidelines** - when to use llm_generate for interactive queries vs silent completion for workflows
- Clarification guidelines (when to ask users for more info)
- Multimodal synthesis instructions with citation format

**Key Files:**
- `capstone/agent_v2/prompts/__init__.py`
- `capstone/agent_v2/prompts/rag_system_prompt.py`
- `capstone/agent_v2/prompts/README.md`
- `capstone/agent_v2/tests/test_rag_system_prompt.py`
- `capstone/agent_v2/tests/integration/test_rag_prompt_integration.py`

**Critical Feature - Response Generation:**
- **Interactive queries** (user asks question) → TodoList includes llm_generate as final step
- **Autonomous workflows** (system task) → No response step, silent completion
- Examples show both patterns clearly

**Prompt Structure:**
```python
RAG_SYSTEM_PROMPT = """
# RAG Knowledge Assistant - System Instructions

## Your Role
You are a RAG agent specialized in multimodal knowledge retrieval...

## Query Classification
1. LISTING - "Which documents are available?"
2. CONTENT_SEARCH - "How does X work?"
3. DOCUMENT_SUMMARY - "Summarize document Y"
4. METADATA_SEARCH - "Show PDFs from last week"
5. COMPARISON - "Compare report A and B"

## Planning Patterns

### LISTING (Interactive)
TodoList:
1. List documents (rag_list_documents)
2. Respond to user (llm_generate with context) ← KEY!

### CONTENT_SEARCH
TodoList:
1. Search content (rag_semantic_search)
2. Synthesize (llm_generate with search results)

### AUTONOMOUS WORKFLOW
TodoList:
1. Task 1
2. Task 2
(No response step - silent completion)

## Tool Usage Rules
- rag_semantic_search: Content within documents
- rag_list_documents: What documents exist
- rag_get_document: Specific document details
- llm_generate: Formulate user responses (CRITICAL for interactive queries!)

## Response Generation Guidelines
✅ Interactive: Always use llm_generate as final step
❌ Autonomous: No response step

...
"""
```

**Status:** ✅ Story document created, ready for implementation

---

### ✅ Story 1.5: Multimodal Synthesis via PythonTool
**File:** [`story-1.5-multimodal-synthesis.md`](./story-1.5-multimodal-synthesis.md)

**What it delivers:**
- **NO NEW TOOL** - leverages existing PythonTool
- Reference synthesis script in `docs/rag_synthesis_example.py`
- Synthesis guidance in RAG_SYSTEM_PROMPT (Story 1.4)
- Integration test demonstrating search → synthesize workflow
- Two synthesis approaches: **llm_generate** (recommended) or **python_tool** (for complex formatting)

**Key Files:**
- `capstone/agent_v2/docs/rag_synthesis_example.py` (reference implementation)
- `capstone/agent_v2/tests/integration/test_rag_synthesis.py`
- RAG_SYSTEM_PROMPT already includes synthesis patterns (Story 1.4)

**Synthesis Approaches:**

**Option A: llm_generate (Recommended)**
```python
TodoList:
1. Search content (rag_semantic_search)
2. Synthesize response (llm_generate)
   - Input: {
       "prompt": "Synthesize search results into comprehensive answer",
       "context": {"search_results": [...]}
     }
   - Output: Markdown with text + images + citations
```

**Option B: python_tool (For Complex Formatting)**
```python
TodoList:
1. Search content (rag_semantic_search)
2. Generate synthesis code dynamically
3. Execute synthesis (python_tool)
   - Code: <agent-generated Python>
   - Context: {"content_blocks": [...]}
   - Output: Formatted markdown
```

**Why No New Tool?**
- PythonTool already supports code execution with context
- llm_generate handles most synthesis needs
- Agent chooses appropriate approach based on complexity

**Status:** ✅ Story document created, ready for implementation

---

### ✅ Story 1.6: RAG Agent Factory Method and End-to-End Integration
**File:** [`story-1.6-rag-agent-factory-and-integration.md`](./story-1.6-rag-agent-factory-and-integration.md)

**What it delivers:**
- `Agent.create_rag_agent()` static factory method
- One-line RAG agent creation with sensible defaults
- Automatic Azure configuration validation (fail-fast)
- Complete end-to-end integration tests for all query types
- README documentation with usage examples

**Key Files:**
- `capstone/agent_v2/agent.py` (add `create_rag_agent()` method)
- `capstone/agent_v2/README.md` (updated with RAG usage)
- `capstone/agent_v2/tests/test_rag_agent_factory.py` (unit tests)
- `capstone/agent_v2/tests/integration/test_rag_end_to_end.py` (integration tests)

**Factory Method Signature:**
```python
@staticmethod
def create_rag_agent(
    name: str,
    description: str,
    mission: str,
    work_dir: str,
    llm,
    user_context: Optional[Dict[str, Any]] = None,
    include_standard_tools: bool = True,
    azure_config: Optional[Dict[str, str]] = None
) -> "Agent":
    """
    Create RAG-enabled agent with all necessary tools and prompt.
    
    Automatically:
    - Validates Azure Search configuration
    - Instantiates all RAG tools (semantic search, document tools, LLM)
    - Sets RAG_SYSTEM_PROMPT
    - Configures user context for security
    - Optionally includes standard tools (Web, File, Git, Python)
    """
```

**One-Line Agent Creation:**
```python
agent = Agent.create_rag_agent(
    name="Knowledge Assistant",
    description="Multimodal RAG agent for technical docs",
    mission="Answer user questions about documentation",
    work_dir="./rag_sessions",
    llm=my_llm,
    user_context={"user_id": "user123", "org_id": "acme", "scope": "shared"}
)
# Agent ready with all RAG capabilities!
```

**End-to-End Test Scenarios:**
1. **LISTING:** "Welche Dokumente gibt es?"
   - TodoList: [rag_list_documents, llm_generate]
   - Result: Natural language list of documents

2. **CONTENT_SEARCH:** "How does the safety valve work?"
   - TodoList: [rag_semantic_search, llm_generate]
   - Result: Comprehensive answer with diagrams + citations

3. **DOCUMENT_SUMMARY:** "Summarize the installation manual"
   - TodoList: [rag_list_documents, rag_get_document, llm_generate]
   - Result: Document summary

4. **Error Handling:** Missing Azure config, invalid params, etc.

**Backward Compatibility:**
- Agent.create_agent() unchanged (if exists)
- Non-RAG agents unaffected
- Both factory methods coexist

**Status:** ✅ Story document created, ready for implementation

---

## Testing Strategy

### Unit Tests
**Location:** `capstone/agent_v2/tests/`

Each story includes comprehensive unit tests with mocked dependencies:
- Story 1.1: Azure SDK base infrastructure
- Story 1.2: Semantic search tool
- Story 1.3: Document metadata tools
- Story 1.4: RAG system prompt (structure validation)

**Run all unit tests:**
```bash
pytest capstone/agent_v2/tests/ -v --ignore=tests/integration
```

---

### Integration Tests
**Location:** `capstone/agent_v2/tests/integration/`

Integration tests require Azure AI Search credentials:

**Setup:**
```bash
export AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
export AZURE_SEARCH_API_KEY=your-key
export AZURE_SEARCH_CONTENT_INDEX=content-blocks
export AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata
```

**Run integration tests:**
```bash
pytest capstone/agent_v2/tests/integration/ -v -m integration
```

**Integration Test Coverage:**
- Story 1.1: Basic Azure connection + search
- Story 1.2: Real semantic search against index
- Story 1.3: Real document metadata queries
- Story 1.5: Search → synthesis workflow
- Story 1.6: Complete RAG agent end-to-end

---

### Regression Tests

**After each story, verify:**
```bash
# Run ALL existing tests (should still pass)
pytest capstone/agent_v2/tests/ -v

# Verify existing agent still works
python -c "
from capstone.agent_v2.agent import Agent
agent = Agent.create_agent(
    name='Test',
    description='Test',
    system_prompt=None,
    mission='Test',
    work_dir='./test',
    llm=None
)
print(f'✅ Backward compatibility: {len(agent.tools)} tools available')
"
```

---

## Development Workflow

### For Each Story:

1. **Read Implementation Document**
   - Review acceptance criteria
   - Understand integration points
   - Check dependencies

2. **Setup Environment**
   ```bash
   cd capstone/agent_v2
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Implement Story**
   - Follow checklist in story document
   - Run tests frequently
   - Verify integration points

4. **Test Thoroughly**
   ```bash
   # Unit tests
   pytest tests/test_<your_module>.py -v

   # Integration tests (if applicable)
   pytest tests/integration/test_<your_module>.py -v -m integration

   # Regression tests
   pytest tests/ -v --ignore=tests/integration
   ```

5. **Code Quality**
   ```bash
   # Format code
   black capstone/agent_v2/tools/<your_module>.py
   isort capstone/agent_v2/tools/<your_module>.py

   # Type checking
   mypy capstone/agent_v2/tools/<your_module>.py
   ```

6. **Verify Integration**
   - Check all Integration Verification criteria in story
   - Test with existing agent functionality
   - Confirm no regressions

7. **Mark Story Complete**
   - All acceptance criteria met ✅
   - All tests passing ✅
   - Code quality checks passed ✅
   - Documentation updated ✅

---

## Environment Setup

### Required Environment Variables

```bash
# Azure AI Search (Required for RAG features)
export AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
export AZURE_SEARCH_API_KEY=your-api-key

# Optional (have defaults)
export AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata
export AZURE_SEARCH_CONTENT_INDEX=content-blocks
```

### Development Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Development tools (optional)
pip install black isort mypy pytest-asyncio pytest-mock
```

---

## Quick Reference

### File Structure After All Stories

```
capstone/agent_v2/
├── agent.py                           # Modified: Added create_rag_agent() (Story 1.6)
├── requirements.txt                    # Modified: Added Azure SDK (Story 1.1)
├── prompts/                           # NEW (Story 1.4)
│   ├── __init__.py
│   ├── rag_system_prompt.py          # Complete RAG intelligence
│   └── README.md                      # Prompt documentation
├── tools/
│   ├── azure_search_base.py           # NEW (Story 1.1)
│   ├── rag_semantic_search_tool.py    # NEW (Story 1.2)
│   ├── rag_list_documents_tool.py     # NEW (Story 1.3)
│   ├── rag_get_document_tool.py       # NEW (Story 1.3)
│   ├── llm_tool.py                    # NEW (Story 1.3.1)
│   └── [existing tools unchanged]
├── docs/
│   └── rag_synthesis_example.py       # NEW (Story 1.5) - Reference implementation
└── tests/
    ├── test_azure_search_base.py      # NEW (Story 1.1)
    ├── test_rag_semantic_search_tool.py  # NEW (Story 1.2)
    ├── test_rag_document_tools.py     # NEW (Story 1.3)
    ├── test_llm_tool.py               # NEW (Story 1.3.1)
    ├── test_rag_system_prompt.py      # NEW (Story 1.4)
    ├── test_rag_agent_factory.py      # NEW (Story 1.6)
    └── integration/
        ├── test_azure_search_integration.py  # NEW (Story 1.1)
        ├── test_rag_document_tools_integration.py  # NEW (Story 1.3)
        ├── test_llm_tool_integration.py   # NEW (Story 1.3.1)
        ├── test_rag_prompt_integration.py  # NEW (Story 1.4)
        ├── test_rag_synthesis.py         # NEW (Story 1.5)
        └── test_rag_end_to_end.py        # NEW (Story 1.6)
```

---

## Success Metrics

Track these metrics as you complete stories:

### Development Velocity
- ✅ Stories completed on time
- ✅ Minimal rework needed
- ✅ Test coverage ≥80%

### Quality Metrics
- ✅ All tests passing
- ✅ No regressions introduced
- ✅ Code coverage maintained

### Integration Success
- ✅ Backward compatibility preserved (existing Agent.create_agent() works)
- ✅ RAG agent initialization <1 second
- ✅ Search queries <2 seconds

---

## Support and Questions

### Common Issues

**Issue:** Azure SDK import errors
**Solution:** Ensure `pip install azure-search-documents>=11.4.0`

**Issue:** Integration tests fail with authentication error
**Solution:** Verify environment variables are set correctly

**Issue:** Existing tests fail after adding RAG features
**Solution:** Check for import issues or unintended side effects in `__init__.py`

### Getting Help

- Review the detailed story implementation document
- Check PRD for requirements context: `../rag_agent_enhancement_prd/`
- Review existing code patterns in `tools/web_tool.py`, `agent.py`

---

**Ready to start development! Begin with Story 1.1 📋**
