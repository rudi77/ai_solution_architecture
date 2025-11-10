"""Reference implementation for multimodal content synthesis.

This module demonstrates how to synthesize multimodal content blocks (text + images)
retrieved from rag_semantic_search into cohesive, well-formatted markdown responses.

This is a REFERENCE IMPLEMENTATION only - not meant to be imported or used directly.
The agent can generate similar synthesis code dynamically using PythonTool, or use
llm_generate for synthesis (recommended approach).

Usage Patterns:
    
    Option A (Recommended): Use llm_generate for synthesis
    -------------------------------------------------------
    1. Agent calls rag_semantic_search to get content blocks
    2. Agent calls llm_generate with search results as context
    3. LLM synthesizes cohesive response with proper citations
    
    Option B: Use PythonTool with dynamically generated code
    ---------------------------------------------------------
    1. Agent calls rag_semantic_search to get content blocks
    2. Agent generates synthesis code (similar to functions below)
    3. Agent calls PythonTool with code and content_blocks as context
    4. PythonTool executes and returns markdown
    
Example integration in agent workflow:
    
    # After rag_semantic_search returns content_blocks...
    
    # Option A (simpler):
    result = llm_generate(
        prompt="Synthesize these search results into a comprehensive answer...",
        context={"search_results": content_blocks, "query": user_query}
    )
    
    # Option B (more control):
    synthesis_code = generate_synthesis_code()  # Agent generates this
    result = python_tool(
        code=synthesis_code,
        context={"content_blocks": content_blocks, "user_query": user_query}
    )
"""

from typing import List, Dict, Any, Optional


def synthesize_multimodal_response(
    content_blocks: List[Dict[str, Any]], 
    user_query: str,
    max_blocks: int = 10
) -> str:
    """Synthesize multimodal content blocks into markdown response.
    
    This function takes raw content blocks from rag_semantic_search and combines
    them into a cohesive markdown document with:
    - Narrative flow connecting different content pieces
    - Embedded images using markdown syntax
    - Proper source citations for every fact
    - Professional formatting
    
    Args:
        content_blocks: List of content block dictionaries with keys:
            - block_type (str): 'text' or 'image'
            - content_text (str): Text content (if block_type=='text')
            - image_url (str): Image URL (if block_type=='image')
            - image_caption (str): Image description (if block_type=='image')
            - document_title (str): Source document filename
            - page_number (int): Page number in source document
            - score (float): Relevance score (0.0 to 1.0)
        user_query: Original user question/query
        max_blocks: Maximum number of content blocks to include (default: 10)
    
    Returns:
        Markdown-formatted string with embedded images and source citations
        
    Example:
        >>> blocks = [
        ...     {
        ...         "block_type": "text",
        ...         "content_text": "The XYZ pump operates using centrifugal force...",
        ...         "document_title": "technical-manual.pdf",
        ...         "page_number": 45,
        ...         "score": 0.92
        ...     },
        ...     {
        ...         "block_type": "image",
        ...         "image_url": "https://storage.example.com/pump-diagram.jpg",
        ...         "image_caption": "XYZ Pump schematic diagram",
        ...         "document_title": "technical-manual.pdf",
        ...         "page_number": 46,
        ...         "score": 0.88
        ...     }
        ... ]
        >>> result = synthesize_multimodal_response(blocks, "How does the XYZ pump work?")
        >>> print(result)
        # Answer to: How does the XYZ pump work?
        
        The XYZ pump operates using centrifugal force...
        
        *(Source: technical-manual.pdf, p. 45)*
        
        ![XYZ Pump schematic diagram](https://storage.example.com/pump-diagram.jpg)
        
        *(Source: technical-manual.pdf, p. 46)*
    """
    # Start with heading
    markdown = f"# Answer to: {user_query}\n\n"
    
    # Sort blocks by relevance score (highest first)
    sorted_blocks = sorted(
        content_blocks, 
        key=lambda x: x.get('score', 0.0), 
        reverse=True
    )
    
    # Limit to top N most relevant blocks
    top_blocks = sorted_blocks[:max_blocks]
    
    # Process each content block
    for block in top_blocks:
        block_type = block.get('block_type', 'text')
        
        if block_type == 'text':
            # Add text content
            content = block.get('content_text', '').strip()
            if content:
                markdown += f"{content}\n\n"
                
                # Add source citation
                doc_title = block.get('document_title', 'Unknown source')
                page_num = block.get('page_number', '?')
                markdown += f"*(Source: {doc_title}, p. {page_num})*\n\n"
        
        elif block_type == 'image':
            # Add image with caption
            image_url = block.get('image_url', '')
            caption = block.get('image_caption', 'Diagram')
            
            if image_url:
                markdown += f"![{caption}]({image_url})\n\n"
                
                # Add source citation for image
                doc_title = block.get('document_title', 'Unknown source')
                page_num = block.get('page_number', '?')
                markdown += f"*(Source: {doc_title}, p. {page_num})*\n\n"
    
    return markdown.strip()


def synthesize_text_only_response(
    content_blocks: List[Dict[str, Any]], 
    user_query: str,
    max_blocks: int = 10
) -> str:
    """Synthesize text-only content blocks (no images).
    
    Simplified version for text-only results. Filters out image blocks
    and focuses on combining text content into a cohesive response.
    
    Args:
        content_blocks: List of content block dictionaries
        user_query: Original user question
        max_blocks: Maximum text blocks to include
        
    Returns:
        Markdown-formatted text response with citations
    """
    markdown = f"# Answer to: {user_query}\n\n"
    
    # Filter to text blocks only
    text_blocks = [b for b in content_blocks if b.get('block_type') == 'text']
    
    # Sort by relevance
    sorted_blocks = sorted(text_blocks, key=lambda x: x.get('score', 0.0), reverse=True)
    
    # Process top blocks
    for block in sorted_blocks[:max_blocks]:
        content = block.get('content_text', '').strip()
        if content:
            markdown += f"{content}\n\n"
            doc_title = block.get('document_title', 'Unknown source')
            page_num = block.get('page_number', '?')
            markdown += f"*(Source: {doc_title}, p. {page_num})*\n\n"
    
    return markdown.strip()


def synthesize_with_grouping(
    content_blocks: List[Dict[str, Any]],
    user_query: str,
    max_blocks: int = 10
) -> str:
    """Synthesize content with intelligent grouping by document/topic.
    
    This advanced version groups content blocks by source document,
    creating a more organized response structure.
    
    Args:
        content_blocks: List of content block dictionaries
        user_query: Original user question
        max_blocks: Maximum blocks to include (distributed across groups)
        
    Returns:
        Markdown response with grouped content sections
    """
    markdown = f"# Answer to: {user_query}\n\n"
    
    # Sort by relevance first
    sorted_blocks = sorted(
        content_blocks,
        key=lambda x: x.get('score', 0.0),
        reverse=True
    )[:max_blocks]
    
    # Group by document
    from collections import defaultdict
    doc_groups = defaultdict(list)
    
    for block in sorted_blocks:
        doc_title = block.get('document_title', 'Unknown')
        doc_groups[doc_title].append(block)
    
    # Output each document group
    for doc_title, blocks in doc_groups.items():
        markdown += f"## From: {doc_title}\n\n"
        
        for block in blocks:
            if block.get('block_type') == 'text':
                content = block.get('content_text', '').strip()
                if content:
                    markdown += f"{content}\n\n"
                    page_num = block.get('page_number', '?')
                    markdown += f"*(p. {page_num})*\n\n"
            
            elif block.get('block_type') == 'image':
                image_url = block.get('image_url', '')
                caption = block.get('image_caption', 'Diagram')
                if image_url:
                    markdown += f"![{caption}]({image_url})\n\n"
                    page_num = block.get('page_number', '?')
                    markdown += f"*(p. {page_num})*\n\n"
        
        markdown += "---\n\n"
    
    return markdown.strip()


def handle_empty_results(user_query: str) -> str:
    """Generate appropriate message when no search results found.
    
    Args:
        user_query: Original user question
        
    Returns:
        Friendly "no results" message
    """
    return f"""# Answer to: {user_query}

I couldn't find any relevant information in the available documents to answer your question.

**Suggestions:**
- Try rephrasing your question with different keywords
- Check if the topic is covered in the document collection
- Verify document names or references if you're looking for something specific

Would you like to try a different search or browse available documents?"""


def validate_content_block(block: Dict[str, Any]) -> bool:
    """Validate that a content block has required fields.
    
    Args:
        block: Content block dictionary to validate
        
    Returns:
        True if block is valid, False otherwise
    """
    # Must have block_type
    if 'block_type' not in block:
        return False
    
    block_type = block['block_type']
    
    # Text blocks must have content_text
    if block_type == 'text' and not block.get('content_text'):
        return False
    
    # Image blocks must have image_url
    if block_type == 'image' and not block.get('image_url'):
        return False
    
    # Should have document metadata (but not strictly required)
    return True


# Example usage demonstration
if __name__ == "__main__":
    # Example content blocks (as returned from rag_semantic_search)
    example_blocks = [
        {
            "block_id": "block_001",
            "block_type": "text",
            "content_text": "The XYZ pump operates using a centrifugal mechanism that creates pressure differentials to move fluids through the system. The pump is designed for high-efficiency operation in industrial applications.",
            "document_id": "doc_tech_manual",
            "document_title": "technical-manual.pdf",
            "page_number": 45,
            "chunk_number": 12,
            "score": 0.92
        },
        {
            "block_id": "block_002",
            "block_type": "image",
            "image_url": "https://storage.example.com/diagrams/pump-schematic.jpg",
            "image_caption": "XYZ Pump schematic showing inlet, impeller, and outlet components",
            "document_id": "doc_tech_manual",
            "document_title": "technical-manual.pdf",
            "page_number": 46,
            "chunk_number": 13,
            "score": 0.88
        },
        {
            "block_id": "block_003",
            "block_type": "text",
            "content_text": "The pump's efficiency is optimized through variable speed control, allowing adjustment based on system demand. Maximum flow rate is 500 GPM at 1750 RPM.",
            "document_id": "doc_operations",
            "document_title": "operations-guide.pdf",
            "page_number": 12,
            "chunk_number": 5,
            "score": 0.85
        },
        {
            "block_id": "block_004",
            "block_type": "text",
            "content_text": "Regular maintenance includes checking seal integrity, inspecting impeller for wear, and verifying motor alignment. Maintenance should be performed quarterly.",
            "document_id": "doc_maintenance",
            "document_title": "maintenance-schedule.pdf",
            "page_number": 8,
            "chunk_number": 3,
            "score": 0.78
        }
    ]
    
    user_question = "How does the XYZ pump work?"
    
    # Demonstrate basic synthesis
    print("=" * 80)
    print("BASIC SYNTHESIS")
    print("=" * 80)
    result = synthesize_multimodal_response(example_blocks, user_question)
    print(result)
    print("\n")
    
    # Demonstrate grouped synthesis
    print("=" * 80)
    print("GROUPED SYNTHESIS")
    print("=" * 80)
    result_grouped = synthesize_with_grouping(example_blocks, user_question)
    print(result_grouped)
    print("\n")
    
    # Demonstrate empty results handling
    print("=" * 80)
    print("EMPTY RESULTS")
    print("=" * 80)
    empty_result = handle_empty_results("How does the quantum flux capacitor work?")
    print(empty_result)

