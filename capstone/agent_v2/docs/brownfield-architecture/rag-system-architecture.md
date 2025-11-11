# RAG System Architecture

### Overview

RAG capabilities enable enterprise document Q&A through Azure AI Search integration. System supports:
- Multimodal content retrieval (text + images)
- Semantic search with relevance scoring
- Document metadata search and filtering
- LLM-based content synthesis with citations

### RAG Agent Specialization

**Factory Method**: `Agent.create_rag_agent()` in `agent.py`

**System Prompt**: `prompts/rag_system_prompt.py:24-300+` (14KB file)

**Prompt Focus**:
- Tool selection expertise (which tool for which query type)
- Query classification (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON, AUTONOMOUS_WORKFLOW)
- Synthesis guidance (combining multimodal results with citations)
- **NOT planning** - planning handled by Agent orchestrator

### Multimodal Synthesis Workflow

**Standard Pattern** (from README.md):
```
User Query: "How does the XYZ pump work?"
    ↓
Step 1: Semantic Search (rag_semantic_search)
    Returns: List of text + image content blocks with metadata
    ↓
Step 2: Synthesize Response (llm_generate OR python_tool)
    Returns: Cohesive markdown with embedded images and citations
    ↓
Output: Markdown with text + ![images] + (Source: file, p. N)
```

**Synthesis Approaches**:

1. **LLM-based (Recommended)**: Use `LLMTool`
   - Pros: Natural narrative flow, context understanding, simpler
   - Cons: LLM cost for synthesis step

2. **Programmatic**: Use `PythonTool` with generated code
   - Pros: Precise formatting, deterministic, no LLM cost
   - Cons: More complex, requires code generation

### Content Block Structure

**Returned by SemanticSearchTool**:
```python
{
    "block_id": "unique-id",
    "block_type": "text" | "image",
    "content_text": "...",          # If text block
    "image_url": "...",              # If image block
    "image_caption": "...",          # If image block
    "document_id": "...",
    "document_title": "filename.pdf",
    "page_number": 12,
    "chunk_number": 5,
    "score": 0.85                    # Relevance score (0.0-1.0)
}
```

### Citation Format

**Standard** (enforced by RAG system prompt):
```markdown
The XYZ pump operates using a centrifugal mechanism...

*(Source: technical-manual.pdf, p. 45)*

![Diagram showing XYZ pump components](https://storage.example.com/diagram.jpg)

*(Source: technical-manual.pdf, p. 46)*
```

### Azure AI Search Configuration

**Environment Variables** (required):
- `AZURE_SEARCH_ENDPOINT`: `https://your-search.search.windows.net`
- `AZURE_SEARCH_KEY`: API key
- `AZURE_SEARCH_INDEX`: Index name

**Security Filtering** (mentioned in README):
- `user_context` parameter: `{user_id, org_id, scope}`
- Filters search results by user permissions
- Implementation in `azure_search_base.py`

---
