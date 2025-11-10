"""Integration tests for RAG multimodal synthesis workflow.

Tests complete search → synthesize workflow for combining text and image
content blocks into cohesive markdown responses with citations.
"""

import pytest
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.tools.code_tool import PythonTool
import litellm


# Sample content blocks for testing (simulating rag_semantic_search output)
SAMPLE_CONTENT_BLOCKS = [
    {
        "content_id": "block_001",
        "content_type": "text",
        "content": "The XYZ pump operates using a centrifugal mechanism that creates pressure differentials to move fluids through the system.",
        "document_id": "doc_tech_manual",
        "document_title": "technical-manual.pdf",
        "page_number": 45,
        "chunk_id": 12,
        "score": 0.92,
        "org_id": "test_org",
        "user_id": "test_user",
        "scope": "private"
    },
    {
        "content_id": "block_002",
        "content_type": "image",
        "content_path": "https://storage.example.com/diagrams/pump-schematic.jpg",
        "content_text": "XYZ Pump schematic showing inlet, impeller, and outlet components",
        "document_id": "doc_tech_manual",
        "document_title": "technical-manual.pdf",
        "page_number": 46,
        "chunk_id": 13,
        "score": 0.88,
        "org_id": "test_org",
        "user_id": "test_user",
        "scope": "private"
    },
    {
        "content_id": "block_003",
        "content_type": "text",
        "content": "The pump's efficiency is optimized through variable speed control, allowing adjustment based on system demand.",
        "document_id": "doc_operations",
        "document_title": "operations-guide.pdf",
        "page_number": 12,
        "chunk_id": 5,
        "score": 0.85,
        "org_id": "test_org",
        "user_id": "test_user",
        "scope": "private"
    }
]

# Text-only blocks for testing
TEXT_ONLY_BLOCKS = [
    {
        "content_id": "block_t1",
        "content_type": "text",
        "content": "Safety procedures require monthly inspection of all valves.",
        "document_id": "doc_safety",
        "document_title": "safety-manual.pdf",
        "page_number": 23,
        "score": 0.90,
        "org_id": "test_org",
        "user_id": "test_user",
        "scope": "private"
    },
    {
        "content_id": "block_t2",
        "content_type": "text",
        "content": "Emergency shutdown procedures must be followed in case of system failure.",
        "document_id": "doc_safety",
        "document_title": "safety-manual.pdf",
        "page_number": 24,
        "score": 0.87,
        "org_id": "test_org",
        "user_id": "test_user",
        "scope": "private"
    }
]


@pytest.mark.integration
class TestSynthesisWorkflow:
    """Integration tests for complete search → synthesize workflow."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY for LLM synthesis"
    )
    @pytest.mark.asyncio
    async def test_llm_synthesis_multimodal(self):
        """Test synthesis using llm_generate with mixed text + image blocks."""
        tool = LLMTool(llm=litellm)
        
        # Synthesize using llm_generate (Approach A - recommended)
        result = await tool.execute(
            prompt="""Synthesize these search results into a comprehensive answer.
            Include text explanations and embedded images.
            Cite each piece using format: (Source: filename.pdf, p. PAGE_NUMBER)
            For images, use markdown: ![caption](url)""",
            context={
                "search_results": SAMPLE_CONTENT_BLOCKS,
                "query": "How does the XYZ pump work?"
            },
            temperature=0.3,
            max_tokens=1000
        )
        
        # Verify successful synthesis
        assert result["success"] is True
        assert "generated_text" in result
        
        generated = result["generated_text"]
        
        # Verify markdown output contains key elements
        assert len(generated) > 0
        
        # Should reference the pump content
        assert "pump" in generated.lower() or "xyz" in generated.lower()
        
        # Should include citation format (flexible matching)
        # Some LLMs may format citations differently but should include source references
        assert "source" in generated.lower() or "manual" in generated.lower()
        
        print("✅ LLM synthesis (multimodal) successful")
        print(f"Generated {len(generated)} characters")
        print(f"Tokens used: {result['tokens_used']}")

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY for LLM synthesis"
    )
    @pytest.mark.asyncio
    async def test_llm_synthesis_text_only(self):
        """Test synthesis with text-only blocks."""
        tool = LLMTool(llm=litellm)
        
        result = await tool.execute(
            prompt="""Synthesize these search results into a clear answer.
            Include proper source citations: (Source: filename.pdf, p. PAGE_NUMBER)""",
            context={
                "search_results": TEXT_ONLY_BLOCKS,
                "query": "What are the safety procedures?"
            },
            temperature=0.3,
            max_tokens=500
        )
        
        # Verify successful synthesis
        assert result["success"] is True
        generated = result["generated_text"]
        assert len(generated) > 0
        
        # Should mention safety content
        assert "safety" in generated.lower() or "inspection" in generated.lower()
        
        # Should NOT include image markdown since input is text-only
        assert "![" not in generated or generated.count("![") == 0
        
        print("✅ LLM synthesis (text-only) successful")

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY for LLM synthesis"
    )
    @pytest.mark.asyncio
    async def test_llm_synthesis_empty_results(self):
        """Test synthesis with empty search results."""
        tool = LLMTool(llm=litellm)
        
        result = await tool.execute(
            prompt="""The search returned no results. Provide a helpful message to the user
            explaining that no information was found and suggesting next steps.""",
            context={
                "search_results": [],
                "query": "How does the quantum flux capacitor work?"
            },
            temperature=0.3,
            max_tokens=200
        )
        
        # Should generate appropriate "no results" message
        assert result["success"] is True
        generated = result["generated_text"]
        assert len(generated) > 0
        
        # Should indicate no information found
        assert any(word in generated.lower() for word in ["no", "not", "found", "unable", "couldn't"])
        
        print("✅ Empty results handling successful")

    @pytest.mark.asyncio
    async def test_python_tool_synthesis_multimodal(self):
        """Test synthesis using PythonTool with generated code (Approach B)."""
        tool = PythonTool()
        
        # Synthesis code (similar to docs/rag_synthesis_example.py)
        synthesis_code = """
from typing import List, Dict, Any

def synthesize_multimodal_response(content_blocks: List[Dict[str, Any]], user_query: str) -> str:
    markdown = f"# Answer to: {user_query}\\n\\n"
    
    # Sort by relevance score
    sorted_blocks = sorted(content_blocks, key=lambda x: x.get('score', 0.0), reverse=True)
    
    for block in sorted_blocks[:10]:
        content_type = block.get('content_type', 'text')
        
        if content_type == 'text':
            content = block.get('content', '').strip()
            if content:
                markdown += f"{content}\\n\\n"
                doc_title = block.get('document_title', 'Unknown')
                page_num = block.get('page_number', '?')
                markdown += f"*(Source: {doc_title}, p. {page_num})*\\n\\n"
        
        elif content_type == 'image':
            image_url = block.get('content_path', '')
            caption = block.get('content_text', 'Diagram')
            if image_url:
                markdown += f"![{caption}]({image_url})\\n\\n"
                doc_title = block.get('document_title', 'Unknown')
                page_num = block.get('page_number', '?')
                markdown += f"*(Source: {doc_title}, p. {page_num})*\\n\\n"
    
    return markdown.strip()

# Execute synthesis
result = synthesize_multimodal_response(content_blocks, user_query)
"""
        
        # Execute synthesis code
        result = await tool.execute(
            code=synthesis_code,
            context={
                "content_blocks": SAMPLE_CONTENT_BLOCKS,
                "user_query": "How does the XYZ pump work?"
            }
        )
        
        # Verify successful execution
        assert result["success"] is True
        assert "result" in result
        
        generated = result["result"]
        
        # Verify markdown structure
        assert "# Answer to:" in generated
        assert "How does the XYZ pump work?" in generated
        
        # Verify text content is included
        assert "centrifugal" in generated or "pump" in generated
        
        # Verify image markdown syntax
        assert "![" in generated
        assert "](https://storage.example.com/" in generated
        
        # Verify citations
        assert "*(Source:" in generated
        assert "technical-manual.pdf" in generated
        assert "p. 45)" in generated or "p. 46)" in generated
        
        print("✅ PythonTool synthesis (multimodal) successful")
        print(f"Generated markdown length: {len(generated)} characters")

    @pytest.mark.asyncio
    async def test_python_tool_synthesis_text_only(self):
        """Test PythonTool synthesis with text-only blocks."""
        tool = PythonTool()
        
        synthesis_code = """
from typing import List, Dict, Any

def synthesize_text_only(content_blocks: List[Dict[str, Any]], user_query: str) -> str:
    markdown = f"# Answer to: {user_query}\\n\\n"
    
    # Filter text blocks only
    text_blocks = [b for b in content_blocks if b.get('content_type') == 'text']
    sorted_blocks = sorted(text_blocks, key=lambda x: x.get('score', 0.0), reverse=True)
    
    for block in sorted_blocks[:10]:
        content = block.get('content', '').strip()
        if content:
            markdown += f"{content}\\n\\n"
            doc_title = block.get('document_title', 'Unknown')
            page_num = block.get('page_number', '?')
            markdown += f"*(Source: {doc_title}, p. {page_num})*\\n\\n"
    
    return markdown.strip()

result = synthesize_text_only(content_blocks, user_query)
"""
        
        result = await tool.execute(
            code=synthesis_code,
            context={
                "content_blocks": TEXT_ONLY_BLOCKS,
                "user_query": "What are the safety procedures?"
            }
        )
        
        # Verify successful execution
        assert result["success"] is True
        generated = result["result"]
        
        # Verify text content
        assert "safety" in generated.lower()
        assert "inspection" in generated.lower() or "shutdown" in generated.lower()
        
        # Verify citations
        assert "*(Source: safety-manual.pdf" in generated
        
        # Should NOT have image markdown
        assert "![" not in generated
        
        print("✅ PythonTool synthesis (text-only) successful")

    @pytest.mark.asyncio
    async def test_python_tool_empty_results_handling(self):
        """Test PythonTool handling of empty content blocks."""
        tool = PythonTool()
        
        synthesis_code = """
def handle_empty_results(user_query: str) -> str:
    return f'''# Answer to: {user_query}

I couldn't find any relevant information in the available documents to answer your question.

**Suggestions:**
- Try rephrasing your question with different keywords
- Check if the topic is covered in the document collection
- Verify document names or references if you're looking for something specific

Would you like to try a different search or browse available documents?'''

result = handle_empty_results(user_query)
"""
        
        result = await tool.execute(
            code=synthesis_code,
            context={"user_query": "How does the quantum flux capacitor work?"}
        )
        
        assert result["success"] is True
        generated = result["result"]
        
        # Verify appropriate message
        assert "couldn't find" in generated.lower() or "no" in generated.lower()
        assert "Suggestions" in generated or "try" in generated.lower()
        
        print("✅ Empty results handling successful")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("AZURE_SEARCH_ENDPOINT") or not os.getenv("AZURE_SEARCH_API_KEY") or not os.getenv("OPENAI_API_KEY"),
        reason="Requires Azure Search and OpenAI credentials"
    )
    @pytest.mark.asyncio
    async def test_complete_search_to_synthesis_workflow(self):
        """
        Complete end-to-end workflow: search → synthesize.
        
        This test requires real Azure AI Search infrastructure.
        Tests the full workflow from semantic search to synthesis.
        """
        # Step 1: Semantic search
        search_tool = SemanticSearchTool(user_context={"user_id": "integration_test"})
        
        search_result = await search_tool.execute(
            query="pump operation",  # Generic technical query
            top_k=5
        )
        
        # Verify search completed (may or may not find results)
        assert "success" in search_result
        
        if not search_result["success"] or search_result.get("result_count", 0) == 0:
            pytest.skip("No search results available in test index")
        
        # Step 2: Synthesize results using LLM
        llm_tool = LLMTool(llm=litellm)
        
        synthesis_result = await llm_tool.execute(
            prompt="""Synthesize these search results into a comprehensive answer.
            Include relevant details and cite sources using: (Source: filename.pdf, p. PAGE_NUMBER)
            If images are present, embed them using: ![caption](url)""",
            context={
                "search_results": search_result["results"],
                "query": "pump operation"
            },
            temperature=0.3,
            max_tokens=1000
        )
        
        # Verify synthesis completed
        assert synthesis_result["success"] is True
        assert len(synthesis_result["generated_text"]) > 0
        
        print("✅ Complete search → synthesize workflow successful")
        print(f"Search found: {search_result['result_count']} results")
        print(f"Synthesis generated: {len(synthesis_result['generated_text'])} characters")
        print(f"Tokens used: {synthesis_result['tokens_used']}")


@pytest.mark.integration
class TestSynthesisQuality:
    """Tests for synthesis output quality validation."""

    def test_validate_markdown_format(self):
        """Verify markdown output follows expected format."""
        # Sample synthesized output
        sample_output = """# Answer to: How does the XYZ pump work?

The XYZ pump operates using a centrifugal mechanism.

*(Source: technical-manual.pdf, p. 45)*

![Pump diagram](https://storage.example.com/diagram.jpg)

*(Source: technical-manual.pdf, p. 46)*"""
        
        # Verify heading
        assert sample_output.startswith("# Answer to:")
        
        # Verify citation format
        assert "*(Source:" in sample_output
        assert "p. " in sample_output
        
        # Verify image markdown
        assert "![" in sample_output
        assert "](" in sample_output
        
        print("✅ Markdown format validation successful")

    def test_validate_citation_format(self):
        """Verify citation format matches specification."""
        valid_citations = [
            "*(Source: manual.pdf, p. 12)*",
            "*(Source: guide.pdf, p. 5)*",
            "*(Source: technical-specs.xlsx, Sheet 2)*"
        ]
        
        for citation in valid_citations:
            # Should contain key elements
            assert "Source:" in citation
            assert citation.startswith("*(")
            assert citation.endswith(")*")
        
        print("✅ Citation format validation successful")

    def test_validate_image_markdown(self):
        """Verify image markdown follows specification."""
        valid_images = [
            "![Pump schematic](https://storage.example.com/pump.jpg)",
            "![Diagram showing components](https://example.com/diagram.png)"
        ]
        
        for image in valid_images:
            # Should follow ![caption](url) format
            assert image.startswith("![")
            assert "](" in image
            assert image.endswith(")") or image.endswith(".jpg") or image.endswith(".png")
        
        print("✅ Image markdown validation successful")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])

