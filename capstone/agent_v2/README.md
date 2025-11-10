# RAG Agent v2 - Multimodal Knowledge Retrieval

A sophisticated RAG (Retrieval-Augmented Generation) agent framework with multimodal content synthesis capabilities.

## Overview

This agent framework provides intelligent knowledge retrieval from enterprise document collections stored in Azure AI Search. It supports:

- **Multimodal content retrieval**: Text and images from documents
- **Intelligent query classification**: Automatically determines optimal tool sequences
- **Content synthesis**: Combines search results into cohesive, well-cited responses
- **Multiple synthesis approaches**: LLM-based or programmatic synthesis

## Quick Start

```python
from capstone.agent_v2.agent import Agent
from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT
from capstone.agent_v2.tools import (
    rag_semantic_search,
    rag_list_documents,
    rag_get_document,
    llm_generate
)

# Initialize RAG agent
agent = Agent(
    name="rag_assistant",
    system_prompt=RAG_SYSTEM_PROMPT,
    tools=[
        rag_semantic_search,
        rag_list_documents,
        rag_get_document,
        llm_generate
    ],
    model="gpt-4"
)

# Ask a question
response = agent.run("How does the XYZ pump work?")
print(response)
```

## Core Workflow: Multimodal Synthesis

### Complete Search → Synthesize Workflow

When a user asks a content question, the agent follows this pattern:

```
User Query: "How does the XYZ pump work?"
    ↓
Step 1: Semantic Search
    - Tool: rag_semantic_search
    - Returns: List of text + image content blocks with metadata
    ↓
Step 2: Synthesize Response
    - Tool: llm_generate (recommended) OR python_tool
    - Returns: Cohesive markdown with embedded images and citations
    ↓
User receives complete answer with:
    ✓ Text explanations
    ✓ Embedded diagrams/images
    ✓ Source citations for every fact
```

### Example Agent TodoList

```
1. Search for XYZ pump content
   - Tool: rag_semantic_search
   - Input: {"query": "XYZ pump operation functionality", "top_k": 10}
   - Acceptance: ≥3 relevant content blocks retrieved
   - Result: List of text + image blocks with metadata

2. Synthesize multimodal response
   - Tool: llm_generate
   - Input: {
       "prompt": "Synthesize these search results into a comprehensive explanation of how the XYZ pump works, including relevant diagrams",
       "context": {
         "search_results": [...content blocks...],
         "query": "How does the XYZ pump work?"
       }
     }
   - Acceptance: Markdown response with text + images + citations
```

## Synthesis Approaches

### Approach A: llm_generate (Recommended)

**Use when:** You want natural narrative flow and context understanding

**Pros:**
- ✅ Simpler - no code generation needed
- ✅ Better at coherence and narrative flow
- ✅ Handles complex context naturally
- ✅ Easier error handling

**Example:**

```python
# After rag_semantic_search returns content_blocks...
result = llm_generate(
    prompt="""Synthesize these search results into a comprehensive answer.
    Include relevant images with captions and cite all sources using format:
    (Source: filename.pdf, p. PAGE_NUMBER)""",
    context={
        "search_results": content_blocks,
        "query": user_query
    }
)
```

### Approach B: python_tool with Generated Code

**Use when:** You need precise formatting control or deterministic output

**Pros:**
- ✅ Precise formatting control
- ✅ No LLM cost for synthesis step
- ✅ Deterministic, reproducible output

**Example:**

```python
# Agent generates synthesis code dynamically
synthesis_code = """
from typing import List, Dict, Any

def synthesize_multimodal_response(content_blocks: List[Dict[str, Any]], user_query: str) -> str:
    markdown = f"# Answer to: {user_query}\\n\\n"
    
    sorted_blocks = sorted(content_blocks, key=lambda x: x.get('score', 0), reverse=True)
    
    for block in sorted_blocks[:10]:
        if block['block_type'] == 'text':
            content = block.get('content_text', '').strip()
            if content:
                markdown += f"{content}\\n\\n"
                markdown += f"*(Source: {block['document_title']}, p. {block['page_number']})*\\n\\n"
        
        elif block['block_type'] == 'image':
            caption = block.get('image_caption', 'Diagram')
            image_url = block.get('image_url', '')
            if image_url:
                markdown += f"![{caption}]({image_url})\\n\\n"
                markdown += f"*(Source: {block['document_title']}, p. {block['page_number']})*\\n\\n"
    
    return markdown

result = synthesize_multimodal_response(content_blocks, user_query)
"""

# Execute with PythonTool
result = python_tool(
    code=synthesis_code,
    context={"content_blocks": content_blocks, "user_query": user_query}
)
```

## Synthesis Output Format

### Text with Citations

```markdown
The XYZ pump operates using a centrifugal mechanism that creates pressure differentials to move fluids through the system.

*(Source: technical-manual.pdf, p. 45)*
```

### Images with Citations

```markdown
![XYZ Pump schematic showing inlet, impeller, and outlet](https://storage.example.com/pump-diagram.jpg)

*(Source: technical-manual.pdf, p. 46)*
```

### Complete Example Output

```markdown
# Answer to: How does the XYZ pump work?

The XYZ pump operates using a centrifugal mechanism that creates pressure differentials to move fluids through the system.

*(Source: technical-manual.pdf, p. 45)*

![Diagram showing XYZ pump internal components](https://storage.example.com/pump-diagram.jpg)

*(Source: technical-manual.pdf, p. 46)*

The pump's efficiency is optimized through variable speed control, allowing adjustment based on system demand.

*(Source: operations-guide.pdf, p. 12)*
```

## Content Block Structure

Content blocks returned from `rag_semantic_search`:

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

## Synthesis Best Practices

### 1. Prioritize High-Relevance Content

```python
# Sort by score and take top N
sorted_blocks = sorted(content_blocks, key=lambda x: x.get('score', 0), reverse=True)
top_blocks = sorted_blocks[:10]  # Limit to top 10
```

### 2. Always Cite Sources

Every piece of information must include source citation:

```markdown
Content from document...

*(Source: filename.pdf, p. 12)*
```

### 3. Embed Images with Descriptive Captions

```markdown
![Descriptive caption explaining what the image shows](https://url/to/image.jpg)
```

### 4. Handle Edge Cases

```python
# Empty results
if not content_blocks:
    return "No relevant information found. Try rephrasing your query."

# Missing image URLs
image_url = block.get('image_url', '')
if image_url:
    # Include image
else:
    # Skip or use placeholder
```

### 5. Maintain Coherent Flow

When using `llm_generate`, the LLM naturally creates narrative flow. When using `python_tool`, consider:
- Grouping related content together
- Adding transitional text between sections
- Organizing by topic or document source

## Reference Implementation

See `docs/rag_synthesis_example.py` for complete reference implementations including:

- `synthesize_multimodal_response()` - Basic text + image synthesis
- `synthesize_text_only_response()` - Text-only synthesis
- `synthesize_with_grouping()` - Advanced synthesis with document grouping
- `handle_empty_results()` - Empty results handling
- Example usage with sample data

Run the example:

```bash
cd capstone/agent_v2
python docs/rag_synthesis_example.py
```

## Testing

Integration tests demonstrate complete workflows:

```bash
# Run synthesis integration tests
pytest tests/integration/test_rag_synthesis.py -v

# Run all RAG integration tests
pytest tests/integration/ -v -k rag
```

## Architecture

```
User Query
    ↓
Agent (with RAG_SYSTEM_PROMPT)
    ↓
Query Classification
    ↓
TodoList Planning
    ↓
Tool Execution:
    1. rag_semantic_search → Content blocks
    2. llm_generate → Synthesized response
    ↓
Markdown Output (text + images + citations)
```

## Available Tools

### rag_semantic_search
Search for content using semantic similarity.

**Input:** `{"query": str, "top_k": int}`  
**Output:** List of content blocks (text + images)

### rag_list_documents
List available documents with optional filters.

**Input:** `{"filters": dict, "limit": int}`  
**Output:** List of document metadata

### rag_get_document
Get detailed information about a specific document.

**Input:** `{"document_id": str}`  
**Output:** Complete document metadata and summary

### llm_generate
Generate natural language text for synthesis and responses.

**Input:** `{"prompt": str, "context": dict}`  
**Output:** Generated text response

### python_tool
Execute Python code for programmatic synthesis.

**Input:** `{"code": str, "context": dict}`  
**Output:** Code execution result

## Query Types

The RAG system handles multiple query patterns:

1. **LISTING** - "Which documents are available?"
2. **CONTENT_SEARCH** - "How does X work?" ← Synthesis used here
3. **DOCUMENT_SUMMARY** - "Summarize document Y"
4. **METADATA_SEARCH** - "Show PDFs from last week"
5. **COMPARISON** - "Compare document A and B"
6. **AUTONOMOUS_WORKFLOW** - System tasks without user response

See `prompts/rag_system_prompt.py` for complete classification guidelines.

## Configuration

### Azure AI Search Setup

```python
import os

os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://your-search.search.windows.net'
os.environ['AZURE_SEARCH_KEY'] = 'your-api-key'
os.environ['AZURE_SEARCH_INDEX'] = 'your-index-name'
```

### LLM Configuration

```python
agent = Agent(
    name="rag_assistant",
    model="gpt-4",  # or "gpt-4-turbo", "gpt-3.5-turbo"
    temperature=0.7,
    max_tokens=2000
)
```

## Error Handling

### Synthesis Errors

```python
try:
    result = synthesize_multimodal_response(content_blocks, query)
except Exception as e:
    # Fallback to llm_generate
    result = llm_generate(
        prompt="Synthesize these results...",
        context={"search_results": content_blocks}
    )
```

### Empty Search Results

```python
if not content_blocks:
    return {
        "response": "No relevant information found.",
        "suggestions": [
            "Try rephrasing with different keywords",
            "Check available documents with rag_list_documents",
            "Verify document names or references"
        ]
    }
```

### Broken Image URLs

```python
# Skip broken images, include text only
if block['block_type'] == 'image':
    image_url = block.get('image_url', '')
    if image_url and is_url_accessible(image_url):
        markdown += f"![{caption}]({image_url})\n\n"
    else:
        # Skip image or add placeholder
        continue
```

## Performance Considerations

- **Limit content blocks**: Use top 10-15 blocks to keep responses manageable
- **Response length**: Target ~500-1000 tokens for optimal readability
- **Image selection**: Prioritize high-relevance images (score > 0.75)
- **Synthesis timeout**: Allow 5-10 seconds for synthesis step

## Future Enhancements

- Automatic image filtering (remove irrelevant diagrams)
- Content deduplication across sources
- Citation style customization (APA, MLA, etc.)
- Response length control with summarization
- Multi-language synthesis support
- Streaming synthesis for real-time updates

## Contributing

When extending synthesis capabilities:

1. Add new synthesis functions to `docs/rag_synthesis_example.py`
2. Update `RAG_SYSTEM_PROMPT` if agent behavior needs adjustment
3. Add integration tests to `tests/integration/test_rag_synthesis.py`
4. Update this README with new patterns

## License

See main repository LICENSE file.

