# Story 1.5: Multimodal Synthesis via PythonTool - Brownfield Addition

## User Story

**As a** RAG-enabled agent,
**I want** to synthesize retrieved content blocks into cohesive markdown responses,
**So that** users receive complete answers with embedded images and proper citations without opening source documents.

## Story Context

**Business Context:**
After retrieving multimodal content (text + images) via rag_semantic_search, the agent needs to combine these disparate blocks into a cohesive, well-formatted response. This synthesis step transforms raw search results into user-friendly markdown with:
- Narrative flow connecting different content pieces
- Embedded images with captions
- Proper source citations for every fact
- Professional formatting

Without synthesis capability, users receive fragmented content blocks instead of coherent answers.

**Existing System Integration:**

- **Integrates with:** Existing PythonTool (tools/code_tool.py), RAG_SYSTEM_PROMPT from Story 1.4
- **Technology:** Python code generation, markdown formatting, existing PythonTool infrastructure
- **Follows pattern:** PythonTool already supports context parameter and code execution
- **Touch points:**
  - PythonTool.execute() for running synthesis code
  - RAG_SYSTEM_PROMPT includes synthesis patterns
  - Agent generates Python code dynamically based on search results

**Dependencies:**
- ✅ Story 1.2 must be completed (SemanticSearchTool returns multimodal content blocks)
- ✅ Story 1.4 must be completed (RAG_SYSTEM_PROMPT includes synthesis patterns)
- ✅ Existing PythonTool (tools/code_tool.py) - no modifications needed
- ⚠️ Story 1.3.1 (LLMTool) provides alternative synthesis approach

**Important Design Decision:**
- **NO NEW TOOL REQUIRED** - leverages existing PythonTool
- Agent generates synthesis code dynamically based on results
- RAG_SYSTEM_PROMPT teaches synthesis patterns
- Both PythonTool and LLMTool can be used for synthesis (agent chooses)

## Acceptance Criteria

### Functional Requirements

**AC1.5.1: RAG System Prompt Synthesis Templates**

The RAG_SYSTEM_PROMPT (from Story 1.4) includes synthesis guidance:

1. **When to synthesize**:
   - After rag_semantic_search returns multiple content blocks
   - When text + images need to be combined into coherent response
   - For complex multi-source answers

2. **Synthesis approach options**:
   - **Option A**: Use llm_generate with search results as context (simpler, recommended)
   - **Option B**: Use PythonTool to generate markdown programmatically (for complex formatting)

3. **Synthesis instructions**:
   - Combine text blocks into narrative flow
   - Embed images using markdown: `![caption](url)`
   - Cite sources after each content piece: `(Source: filename.pdf, S. 12)`
   - Preserve factual accuracy - don't invent information
   - Prioritize relevant diagrams for technical content

**AC1.5.2: Reference Synthesis Example Documentation**

A reference script exists in `docs/rag_synthesis_example.py` demonstrating:

```python
def synthesize_multimodal_response(content_blocks, user_query):
    """
    Synthesize multimodal content blocks into markdown response.
    
    Args:
        content_blocks: List of dicts with keys:
            - block_type: 'text' or 'image'
            - content_text: Text content (if block_type=='text')
            - image_url: Image URL (if block_type=='image')
            - image_caption: Image description (if block_type=='image')
            - document_title: Source document filename
            - page_number: Page number in source
            - score: Relevance score
        user_query: Original user question
    
    Returns:
        Markdown string with embedded images and citations
    """
    markdown = f"# Answer to: {user_query}\n\n"
    
    # Group blocks by relevance, prioritize high-scoring content
    sorted_blocks = sorted(content_blocks, key=lambda x: x.get('score', 0), reverse=True)
    
    for block in sorted_blocks[:10]:  # Limit to top 10 most relevant
        if block['block_type'] == 'text':
            content = block.get('content_text', '').strip()
            if content:
                markdown += f"{content}\n\n"
                markdown += f"*(Source: {block['document_title']}, S. {block['page_number']})*\n\n"
        
        elif block['block_type'] == 'image':
            caption = block.get('image_caption', 'Diagram')
            image_url = block.get('image_url', '')
            if image_url:
                markdown += f"![{caption}]({image_url})\n\n"
                markdown += f"*(Source: {block['document_title']}, S. {block['page_number']})*\n\n"
    
    return markdown


# Example usage in agent workflow:
# 1. Agent calls rag_semantic_search
# 2. Agent generates this synthesis code dynamically
# 3. Agent calls PythonTool with code and content_blocks as context
# 4. PythonTool executes and returns markdown
```

**AC1.5.3: Integration with RAG Workflow**

The complete workflow for content search queries:

```
User: "How does the XYZ pump work?"

TodoList:
1. Search for XYZ pump content
   - Tool: rag_semantic_search
   - Input: {"query": "XYZ pump operation functionality", "top_k": 10}
   - Acceptance: ≥3 relevant content blocks retrieved
   - Result: List of text + image blocks with metadata

2. Synthesize multimodal response
   - Tool: llm_generate (recommended) OR python_tool (for complex formatting)
   - Option A (llm_generate):
     Input: {
       "prompt": "Synthesize these search results into a comprehensive explanation of how the XYZ pump works, including relevant diagrams",
       "context": {"search_results": [...content blocks...], "query": "How does the XYZ pump work?"}
     }
   - Option B (python_tool):
     Input: {
       "code": "<dynamically generated synthesis code>",
       "context": {"content_blocks": [...], "user_query": "..."}
     }
   - Acceptance: Markdown response with text + images + citations
```

**AC1.5.4: Synthesis Quality Requirements**

Generated responses must:
- ✅ Include relevant text content from search results
- ✅ Embed images using proper markdown syntax
- ✅ Cite source document and page number for each piece
- ✅ Maintain logical flow and coherence
- ✅ Prioritize high-relevance content (based on search scores)
- ✅ Limit response length (top 10 blocks, ~500-1000 tokens)
- ✅ Not invent information - only use retrieved content
- ✅ Handle both text-only and multimodal results gracefully

**AC1.5.5: Error Handling**

Synthesis step handles edge cases:
- Empty search results → "No relevant information found"
- Image URLs broken → Skip image, include text only
- Missing metadata → Use "Unknown source" fallback
- Synthesis code errors → Fallback to llm_generate approach

### Non-Functional Requirements

**AC1.5.6: No PythonTool Modifications**

- Existing PythonTool works without any code changes
- PythonTool.execute() already supports context parameter
- No new dependencies or tool implementations required

**AC1.5.7: Performance**

- Synthesis step completes in <5 seconds (depends on LLM/Python execution)
- Handles up to 20 content blocks efficiently
- Markdown output size limited to reasonable length (~2000 tokens)

### Testing Requirements

**AC1.5.8: Integration Tests**

Integration test in `tests/integration/test_rag_synthesis.py`:

1. **Complete search → synthesize workflow**:
   - Mock or use real rag_semantic_search
   - Get multimodal content blocks
   - Call llm_generate with blocks as context
   - Verify markdown output contains:
     - Text content from blocks
     - Image markdown syntax (if images present)
     - Source citations
     - Proper formatting

2. **PythonTool synthesis approach**:
   - Generate synthesis code dynamically
   - Call PythonTool with code and content blocks
   - Verify markdown output quality
   - Compare with llm_generate approach

3. **Edge cases**:
   - Empty search results → Appropriate message
   - Text-only results → No image markdown
   - Image-only results → Just images with captions
   - Mixed text + images → Proper interleaving

**AC1.5.9: Example Output Validation**

Test validates output format:

```markdown
# Answer to: How does the XYZ pump work?

The XYZ pump operates using a centrifugal mechanism that creates pressure differentials to move fluids through the system.

*(Source: technical-manual.pdf, S. 45)*

![Diagram showing XYZ pump internal components](https://storage.example.com/pump-diagram.jpg)

*(Source: technical-manual.pdf, S. 46)*

The pump's efficiency is optimized through variable speed control, allowing adjustment based on system demand.

*(Source: operations-guide.pdf, S. 12)*
```

## Definition of Done

### Documentation
- [ ] `docs/rag_synthesis_example.py` created with reference implementation
- [ ] Example includes comprehensive docstrings
- [ ] RAG_SYSTEM_PROMPT (Story 1.4) includes synthesis guidance
- [ ] README.md updated with synthesis workflow example
- [ ] Comments explain when to use llm_generate vs python_tool

### Prompt Content (in Story 1.4)
- [ ] Synthesis instructions section present in RAG_SYSTEM_PROMPT
- [ ] Image embedding syntax specified
- [ ] Source citation format defined
- [ ] Example workflow shows synthesis step
- [ ] Both synthesis approaches documented (llm_generate and python_tool)

### Testing
- [ ] Integration test demonstrates search → synthesize workflow
- [ ] Test validates markdown output format
- [ ] Edge cases tested (empty results, text-only, images-only)
- [ ] Both synthesis approaches tested (llm_generate and python_tool)
- [ ] Output quality validated (citations, images, coherence)

### Integration
- [ ] Synthesis works with existing PythonTool (no modifications)
- [ ] Works with llm_generate from Story 1.3.1
- [ ] RAG agent successfully completes synthesis workflow
- [ ] Markdown output renders correctly in viewers
- [ ] No breaking changes to existing functionality

## Integration Verification

After implementation, verify:

- **IV1.5.1:** Existing PythonTool works without modification for synthesis
- **IV1.5.2:** Agent successfully executes synthesis step using llm_generate
- **IV1.5.3:** Agent can optionally use python_tool for synthesis
- **IV1.5.4:** Final markdown output includes text + images + citations
- **IV1.5.5:** Output is valid markdown and renders correctly
- **IV1.5.6:** Search → synthesize workflow completes end-to-end
- **IV1.5.7:** Synthesis quality meets requirements (coherent, cited, multimodal)

## Technical Notes

### Synthesis Approaches Comparison

**Approach A: llm_generate (Recommended)**

Pros:
- ✅ Simpler - no code generation needed
- ✅ LLM naturally handles narrative flow
- ✅ Better at context understanding and coherence
- ✅ Easier error handling

Cons:
- ⚠️ LLM costs per synthesis
- ⚠️ Less control over exact formatting

Example:
```python
llm_generate(
    prompt="Synthesize these search results into a comprehensive answer with images and citations",
    context={"search_results": content_blocks, "query": user_query}
)
```

**Approach B: python_tool**

Pros:
- ✅ Precise formatting control
- ✅ No LLM cost for synthesis
- ✅ Deterministic output

Cons:
- ⚠️ Agent must generate synthesis code
- ⚠️ Less natural narrative flow
- ⚠️ More complex error handling

Example:
```python
python_tool(
    code=generate_synthesis_code(),  # Agent generates this
    context={"content_blocks": blocks, "user_query": query}
)
```

**Recommendation**: Use **llm_generate** by default, python_tool for specific formatting needs.

### Reference Implementation Location

```
capstone/agent_v2/docs/
├── rag_synthesis_example.py      # Reference synthesis script
└── README.md                      # Synthesis documentation
```

### Markdown Format Standards

**Text blocks**:
```markdown
Content from document...

*(Source: filename.pdf, S. 12)*
```

**Image blocks**:
```markdown
![Caption or description](https://storage.url/image.jpg)

*(Source: filename.pdf, S. 15)*
```

**Combined**:
```markdown
Text explanation...

*(Source: manual.pdf, S. 10)*

![Relevant diagram](https://storage.url/diagram.jpg)

*(Source: manual.pdf, S. 11)*

More text...

*(Source: guide.pdf, S. 5)*
```

### Content Block Structure (from rag_semantic_search)

```python
{
    "block_id": "unique-id",
    "block_type": "text" | "image",
    "content_text": "...",        # If text
    "image_url": "...",            # If image
    "image_caption": "...",        # If image
    "document_id": "...",
    "document_title": "filename.pdf",
    "page_number": 12,
    "chunk_number": 5,
    "score": 0.85
}
```

### Future Enhancements (Out of Scope)

- Automatic image filtering (remove irrelevant diagrams)
- Content deduplication (same text from multiple sources)
- Citation style customization (APA, MLA, etc.)
- Response length control (summarization for long content)
- Multi-language synthesis
- Streaming synthesis for real-time updates

## Risk Assessment

**Low Risk:**
- ✅ No new tools required (uses existing PythonTool)
- ✅ No code changes to existing tools
- ✅ Prompt-based approach - easy to iterate
- ✅ Both synthesis approaches tested

**Considerations:**
- ⚠️ Synthesis quality depends on RAG_SYSTEM_PROMPT quality
- ⚠️ Agent must learn to generate synthesis code (if using python_tool)
- ⚠️ Image URLs must be accessible for rendering

## Dependencies & Prerequisites

**Required:**
- ✅ Story 1.2 complete (SemanticSearchTool returns content blocks)
- ✅ Story 1.4 complete (RAG_SYSTEM_PROMPT includes synthesis patterns)
- ✅ Existing PythonTool functional (tools/code_tool.py)

**Optional:**
- ✅ Story 1.3.1 complete (LLMTool for simpler synthesis)

**Not Required:**
- ❌ New tool implementation
- ❌ PythonTool modifications
- ❌ External synthesis libraries

## Status

**Current Status:** Ready for Implementation

**Next Steps:**
1. Create `docs/rag_synthesis_example.py` reference implementation
2. Verify RAG_SYSTEM_PROMPT includes synthesis guidance (should already exist from Story 1.4)
3. Write integration test for search → synthesize workflow
4. Test both llm_generate and python_tool approaches
5. Validate markdown output quality

---

## Dev Agent Record

**Status:** Not Started

**Agent Model Used:** N/A

**File List:**
- Created: (will be filled during implementation)
- Modified: (will be filled during implementation)

**Change Log:**
- (will be filled during implementation)

**Completion Notes:**
- (will be filled after implementation)

---

## QA Results

**Status:** Not Reviewed

**QA Agent:** N/A

**Review Date:** N/A

**Findings:**
- (will be filled during QA review)

**Final Status:** N/A

