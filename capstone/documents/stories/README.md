# RAG Agent Enhancement - Story Implementation Documents

This directory contains detailed implementation documents for all user stories in the **Multimodal RAG Knowledge Retrieval for Agent Framework** epic.

---

## Story Overview

| Story | Title | Priority | Estimate | Status | Dependencies |
|-------|-------|----------|----------|--------|--------------|
| **1.1** | Azure AI Search SDK Integration and Base Tool Infrastructure | High | 4-6 hours | ✅ **Ready** | None |
| **1.2** | Semantic Search Tool for Content Blocks | High | 6-8 hours | Pending | 1.1 |
| **1.3** | Document Metadata Tools (List and Get) | Medium | 4-6 hours | Pending | 1.1, 1.2 |
| **1.4** | RAG System Prompt for Query Classification and Planning | High | 6-8 hours | Pending | None |
| **1.5** | Multimodal Synthesis via PythonTool | Medium | 4-5 hours | Pending | 1.2, 1.4 |
| **1.6** | RAG Agent Factory Method and End-to-End Integration | High | 6-8 hours | Pending | All (1.1-1.5) |

**Total Estimate:** 30-41 hours (~1 week for solo developer, ~3-4 days for pair)

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

### 📋 Story 1.3: Document Metadata Tools (List and Get)
**File:** `story-1-3-document-metadata-tools.md` (to be created)

**What it delivers:**
- `ListDocumentsTool` - List documents with filters and sorting
- `GetDocumentTool` - Retrieve single document with summary
- Both tools query `documents-metadata` index
- Security filtering applied automatically

**Key Files:**
- `capstone/agent_v2/tools/rag_list_documents_tool.py`
- `capstone/agent_v2/tools/rag_get_document_tool.py`
- `capstone/agent_v2/tests/test_rag_list_documents_tool.py`
- `capstone/agent_v2/tests/test_rag_get_document_tool.py`

**Tool Interfaces:**
```python
# List documents
list_tool.execute(
    filters={"document_type": "Manual"},
    sort_by="upload_date",
    limit=20,
    user_context={...}
)

# Get specific document
get_tool.execute(
    doc_id="doc-12345",
    user_context={...}
)
```

---

### 📋 Story 1.4: RAG System Prompt for Query Classification and Planning
**File:** `story-1-4-rag-system-prompt.md` (to be created)

**What it delivers:**
- `prompts/rag_system_prompt.py` - Complete RAG intelligence
- Query classification logic (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, etc.)
- Planning patterns for each query type
- Synthesis instructions with citation format
- Clarification guidelines

**Key Files:**
- `capstone/agent_v2/prompts/__init__.py`
- `capstone/agent_v2/prompts/generic_system_prompt.py` (moved from agent.py)
- `capstone/agent_v2/prompts/rag_system_prompt.py`
- `capstone/agent_v2/prompts/README.md`

**Prompt Structure:**
```python
RAG_SYSTEM_PROMPT = """
You are a RAG (Retrieval-Augmented Generation) agent...

## Query Classification
Classify each query into one of these types:
1. LISTING - "What documents are available?"
2. CONTENT_SEARCH - "How does X work?"
3. DOCUMENT_SUMMARY - "Summarize document Y"
4. METADATA_SEARCH - "Show all PDFs from last week"
5. COMPARISON - "Compare report A and B"

## Planning Patterns
[Examples of TodoList structures for each type]

## Synthesis Instructions
- Use PythonTool for synthesis step
- Embed images: ![caption](url)
- Cite sources: (Source: filename.pdf, S. X)
...
"""
```

---

### 📋 Story 1.5: Multimodal Synthesis via PythonTool
**File:** `story-1-5-multimodal-synthesis.md` (to be created)

**What it delivers:**
- Updates to RAG system prompt (from 1.4) with synthesis template
- Reference synthesis script documentation
- Integration test demonstrating search → synthesize workflow
- Validation of markdown output

**Key Files:**
- `capstone/agent_v2/docs/rag_synthesis_example.py` (reference script)
- `capstone/agent_v2/tests/integration/test_rag_synthesis.py`

**Synthesis Flow:**
1. Agent executes `rag_semantic_search` → Gets content blocks
2. Agent plans synthesis step using `PythonTool`
3. Agent generates Python code dynamically to format markdown
4. Final output: Markdown with embedded images + citations

**Example Synthesis Code (Agent-generated):**
```python
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

---

### 📋 Story 1.6: RAG Agent Factory Method and End-to-End Integration
**File:** `story-1-6-rag-agent-factory-and-integration.md` (to be created)

**What it delivers:**
- `Agent.create_rag_agent()` static method
- Full end-to-end integration test
- README documentation with usage examples
- Performance and security verification

**Key Files:**
- `capstone/agent_v2/agent.py` (add `create_rag_agent()` method)
- `capstone/agent_v2/README.md` (updated with RAG usage)
- `capstone/agent_v2/tests/integration/test_rag_end_to_end.py`

**Factory Method Signature:**
```python
@staticmethod
def create_rag_agent(
    name: str,
    description: str,
    mission: str,
    work_dir: str,
    llm,
    user_context: Optional[Dict] = None
) -> "Agent":
    """
    Create a RAG-enabled agent with Azure AI Search tools and RAG system prompt.

    Example:
        agent = Agent.create_rag_agent(
            name="Knowledge Assistant",
            description="Multimodal RAG agent",
            mission="Explain how the safety valve works",
            work_dir="./rag_sessions",
            llm=None,
            user_context={"user_id": "user123", "department": "engineering"}
        )
    """
```

**End-to-End Test Scenarios:**
1. **CONTENT_SEARCH:** "Explain the XYZ process"
   - Agent classifies query
   - Plans: search → synthesize
   - Executes tools
   - Returns markdown with images + citations

2. **DOCUMENT_SUMMARY:** "Summarize the Q3 financial report"
   - Agent asks which report (if multiple)
   - Gets document summary
   - Returns formatted response

3. **LISTING:** "What manuals are available?"
   - Lists documents filtered by type
   - Returns formatted list

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
├── agent.py                           # Modified: Added create_rag_agent()
├── requirements.txt                    # Modified: Added Azure SDK
├── prompts/                           # NEW
│   ├── __init__.py
│   ├── generic_system_prompt.py
│   ├── rag_system_prompt.py
│   └── README.md
├── tools/
│   ├── azure_search_base.py           # NEW (Story 1.1)
│   ├── rag_semantic_search_tool.py    # NEW (Story 1.2)
│   ├── rag_list_documents_tool.py     # NEW (Story 1.3)
│   ├── rag_get_document_tool.py       # NEW (Story 1.3)
│   └── [existing tools unchanged]
├── docs/
│   └── rag_synthesis_example.py       # NEW (Story 1.5)
└── tests/
    ├── test_azure_search_base.py      # NEW (Story 1.1)
    ├── test_rag_semantic_search_tool.py  # NEW (Story 1.2)
    ├── test_rag_list_documents_tool.py   # NEW (Story 1.3)
    ├── test_rag_get_document_tool.py     # NEW (Story 1.3)
    └── integration/
        ├── test_azure_search_integration.py  # NEW (Story 1.1)
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
