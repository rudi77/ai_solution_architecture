"""Unit tests for RAG system prompt.

Tests validate that the RAG_SYSTEM_PROMPT contains all required sections
and components as specified in Story 1.4.
"""

import pytest
from capstone.agent_v2.prompts.rag_system_prompt import (
    RAG_SYSTEM_PROMPT,
    build_rag_system_prompt
)


class TestRagSystemPromptStructure:
    """Test basic structure and validity of RAG_SYSTEM_PROMPT."""

    def test_prompt_is_non_empty_string(self):
        """RAG_SYSTEM_PROMPT should be a non-empty string."""
        assert isinstance(RAG_SYSTEM_PROMPT, str)
        assert len(RAG_SYSTEM_PROMPT) > 0
        assert len(RAG_SYSTEM_PROMPT.strip()) > 0

    def test_prompt_is_valid_python_string(self):
        """RAG_SYSTEM_PROMPT should be a valid Python string (no syntax errors)."""
        # If we can access it and it's a string, it's syntactically valid
        assert isinstance(RAG_SYSTEM_PROMPT, str)

    def test_prompt_has_reasonable_length(self):
        """RAG_SYSTEM_PROMPT should be substantial but not excessive."""
        prompt_length = len(RAG_SYSTEM_PROMPT)
        # Should be at least 5000 characters (comprehensive prompt)
        assert prompt_length > 5000, f"Prompt too short: {prompt_length} chars"
        # Should be less than 30000 characters (reasonable upper bound for comprehensive prompt with examples)
        # Note: ~22k chars = ~5.5k tokens, which is reasonable for a detailed system prompt
        assert prompt_length < 30000, f"Prompt too long: {prompt_length} chars"


class TestRagSystemPromptSections:
    """Test that all required sections are present in RAG_SYSTEM_PROMPT."""

    def test_has_role_definition_section(self):
        """Prompt should define the agent's role."""
        assert "## Your Role" in RAG_SYSTEM_PROMPT or "# Your Role" in RAG_SYSTEM_PROMPT
        assert "RAG" in RAG_SYSTEM_PROMPT
        assert "agent" in RAG_SYSTEM_PROMPT.lower()

    def test_has_tool_selection_guide_section(self):
        """Prompt should include Tool Selection Decision Guide section."""
        assert "## Tool Selection Decision Guide" in RAG_SYSTEM_PROMPT or "Tool Selection" in RAG_SYSTEM_PROMPT
        # Should mention tool selection concepts
        assert "select" in RAG_SYSTEM_PROMPT.lower() or "decision" in RAG_SYSTEM_PROMPT.lower()

    def test_has_tool_usage_rules_section(self):
        """Prompt should include Tool Usage Rules section."""
        assert "## Tool Usage Rules" in RAG_SYSTEM_PROMPT
        # Should mention tools
        assert "tool" in RAG_SYSTEM_PROMPT.lower()

    def test_has_core_principles_section(self):
        """Prompt should include Core Principles Summary section."""
        assert "## Core Principles Summary" in RAG_SYSTEM_PROMPT or "Core Principles" in RAG_SYSTEM_PROMPT
        # Should mention key principles
        assert "principles" in RAG_SYSTEM_PROMPT.lower()

    def test_has_clarification_guidelines_section(self):
        """Prompt should include Clarification Guidelines section."""
        assert "## Clarification Guidelines" in RAG_SYSTEM_PROMPT or "Clarification" in RAG_SYSTEM_PROMPT
        # Should mention asking user
        assert "ask" in RAG_SYSTEM_PROMPT.lower()

    def test_has_multimodal_synthesis_section(self):
        """Prompt should include Multimodal Synthesis/Instructions section."""
        assert ("## Multimodal Synthesis" in RAG_SYSTEM_PROMPT or 
                "## Multimodal" in RAG_SYSTEM_PROMPT or
                "Multimodal" in RAG_SYSTEM_PROMPT)
        # Should mention images
        assert "image" in RAG_SYSTEM_PROMPT.lower()

    def test_has_source_citation_instructions(self):
        """Prompt should include instructions for source citations."""
        assert "citation" in RAG_SYSTEM_PROMPT.lower() or "cite" in RAG_SYSTEM_PROMPT.lower() or "Source:" in RAG_SYSTEM_PROMPT
        # Should show citation format
        assert "Source:" in RAG_SYSTEM_PROMPT


class TestToolMentions:
    """Test that all required RAG tools are mentioned in the prompt."""

    def test_mentions_rag_semantic_search(self):
        """Prompt should mention rag_semantic_search tool."""
        assert "rag_semantic_search" in RAG_SYSTEM_PROMPT

    def test_mentions_rag_list_documents(self):
        """Prompt should mention rag_list_documents tool."""
        assert "rag_list_documents" in RAG_SYSTEM_PROMPT

    def test_mentions_rag_get_document(self):
        """Prompt should mention rag_get_document tool."""
        assert "rag_get_document" in RAG_SYSTEM_PROMPT

    def test_mentions_llm_generate(self):
        """Prompt should mention llm_generate tool."""
        assert "llm_generate" in RAG_SYSTEM_PROMPT

    def test_explains_when_to_use_tools(self):
        """Prompt should explain when to use each tool."""
        # Should have "when to use" or similar guidance
        assert ("when to use" in RAG_SYSTEM_PROMPT.lower() or 
                "use when" in RAG_SYSTEM_PROMPT.lower() or
                "Best for" in RAG_SYSTEM_PROMPT)


class TestToolUsageGuidance:
    """Test that prompt provides clear tool usage guidance."""

    def test_explains_when_to_use_each_tool(self):
        """Prompt should explain when to use each tool."""
        assert "when to use" in RAG_SYSTEM_PROMPT.lower() or "When to use" in RAG_SYSTEM_PROMPT
        # Should mention user expectations
        assert "user" in RAG_SYSTEM_PROMPT.lower()

    def test_emphasizes_llm_generate_for_synthesis(self):
        """Prompt should emphasize using llm_generate for synthesis."""
        # Should have strong language about using llm_generate
        assert "ALWAYS" in RAG_SYSTEM_PROMPT or "always" in RAG_SYSTEM_PROMPT.lower() or "Always" in RAG_SYSTEM_PROMPT
        # Should mention synthesis or answer
        assert "answer" in RAG_SYSTEM_PROMPT.lower() or "synthesis" in RAG_SYSTEM_PROMPT.lower()

    def test_provides_tool_selection_examples(self):
        """Prompt should provide examples of tool selection."""
        # Should mention discovery or content questions
        assert "discovery" in RAG_SYSTEM_PROMPT.lower() or "content" in RAG_SYSTEM_PROMPT.lower()
        # Should guide on matching tools to tasks
        assert "for" in RAG_SYSTEM_PROMPT.lower()


class TestToolSelectionDecisionGuide:
    """Test the Tool Selection Decision Guide section."""

    def test_has_discovery_questions_guidance(self):
        """Prompt should guide on discovery questions."""
        # Should mention discovery or listing
        assert "discovery" in RAG_SYSTEM_PROMPT.lower() or "What documents" in RAG_SYSTEM_PROMPT
        # Should show rag_list_documents usage
        assert "rag_list_documents" in RAG_SYSTEM_PROMPT

    def test_has_content_questions_guidance(self):
        """Prompt should guide on content questions."""
        # Should mention content or how/why questions
        assert "content" in RAG_SYSTEM_PROMPT.lower() or "How does" in RAG_SYSTEM_PROMPT
        # Should show rag_semantic_search usage
        assert "rag_semantic_search" in RAG_SYSTEM_PROMPT

    def test_has_document_specific_guidance(self):
        """Prompt should guide on document-specific queries."""
        # Should mention specific documents
        assert "document" in RAG_SYSTEM_PROMPT.lower()
        # Should show rag_get_document usage
        assert "rag_get_document" in RAG_SYSTEM_PROMPT

    def test_emphasizes_synthesis_with_llm_generate(self):
        """Prompt should emphasize using llm_generate for synthesis."""
        # Count occurrences of llm_generate - should appear multiple times
        llm_generate_count = RAG_SYSTEM_PROMPT.count("llm_generate")
        assert llm_generate_count >= 5, f"llm_generate mentioned only {llm_generate_count} times, expected at least 5"


class TestMultimodalInstructions:
    """Test that prompt includes multimodal (text + images) instructions."""

    def test_has_image_embedding_syntax(self):
        """Prompt should show how to embed images."""
        # Should show markdown image syntax
        assert "![" in RAG_SYSTEM_PROMPT
        assert "](" in RAG_SYSTEM_PROMPT

    def test_has_citation_format(self):
        """Prompt should specify citation format."""
        # Should show (Source: filename, p. X) format
        assert "Source:" in RAG_SYSTEM_PROMPT
        assert "p." in RAG_SYSTEM_PROMPT or "page" in RAG_SYSTEM_PROMPT.lower()

    def test_emphasizes_always_cite_sources(self):
        """Prompt should emphasize always citing sources."""
        # Should have strong language about citations
        assert "always" in RAG_SYSTEM_PROMPT.lower() or "ALWAYS" in RAG_SYSTEM_PROMPT
        assert "cite" in RAG_SYSTEM_PROMPT.lower() or "citation" in RAG_SYSTEM_PROMPT.lower()


class TestBuildRagSystemPrompt:
    """Test the build_rag_system_prompt() parameterization function."""

    def test_function_exists(self):
        """build_rag_system_prompt function should exist."""
        assert callable(build_rag_system_prompt)

    def test_returns_string_with_no_params(self):
        """Function should return valid string when called with no parameters."""
        result = build_rag_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_available_tools(self):
        """Function should include available tools when specified."""
        tools = ["rag_semantic_search", "rag_list_documents"]
        result = build_rag_system_prompt(available_tools=tools)
        
        assert "rag_semantic_search" in result
        assert "rag_list_documents" in result
        # Should have an "Available Tools" section
        assert "Available Tools" in result or "available tools" in result.lower()

    def test_includes_domain_knowledge(self):
        """Function should include domain knowledge when specified."""
        domain = "This is a medical knowledge base."
        result = build_rag_system_prompt(domain_knowledge=domain)
        
        assert domain in result
        # Should have a domain section
        assert "Domain" in result or "domain" in result.lower()

    def test_includes_user_context(self):
        """Function should include user context when specified."""
        context = "User prefers responses in German."
        result = build_rag_system_prompt(user_context=context)
        
        assert context in result
        # Should have a context section
        assert "Context" in result or "context" in result.lower()

    def test_combines_all_parameters(self):
        """Function should handle all parameters together."""
        tools = ["rag_semantic_search"]
        domain = "Medical domain"
        context = "German user"
        
        result = build_rag_system_prompt(
            available_tools=tools,
            domain_knowledge=domain,
            user_context=context
        )
        
        assert "rag_semantic_search" in result
        assert domain in result
        assert context in result

    def test_preserves_base_prompt_content(self):
        """Function should preserve core RAG_SYSTEM_PROMPT content."""
        result = build_rag_system_prompt()

        # Should still have key sections from base prompt
        assert "Tool Selection" in result or "Tool Usage" in result
        assert "rag_semantic_search" in result
        assert "llm_generate" in result


class TestPromptQuality:
    """Test overall quality aspects of the prompt."""

    def test_no_obvious_typos_in_headers(self):
        """Major section headers should be spelled correctly."""
        # Check for common section headers in refactored prompt
        sections = [
            "Your Role", "Tool Usage", "Tool Selection",
            "Clarification", "Multimodal", "Core Principles"
        ]

        # At least most sections should be present
        found_sections = sum(1 for section in sections if section in RAG_SYSTEM_PROMPT)
        assert found_sections >= 4, f"Only found {found_sections} of expected {len(sections)} sections"

    def test_consistent_tool_naming(self):
        """Tool names should be consistent (rag_semantic_search not rag-semantic-search)."""
        # Check that tools use underscore not hyphen
        assert "rag_semantic_search" in RAG_SYSTEM_PROMPT
        assert "rag_list_documents" in RAG_SYSTEM_PROMPT
        assert "rag_get_document" in RAG_SYSTEM_PROMPT
        assert "llm_generate" in RAG_SYSTEM_PROMPT
        
        # Should NOT have hyphenated versions
        assert "rag-semantic-search" not in RAG_SYSTEM_PROMPT
        assert "rag-list-documents" not in RAG_SYSTEM_PROMPT

    def test_has_multiple_examples(self):
        """Prompt should include multiple concrete examples."""
        # Should have several example queries/workflows
        example_count = (RAG_SYSTEM_PROMPT.count("Example") + 
                        RAG_SYSTEM_PROMPT.count("example") +
                        RAG_SYSTEM_PROMPT.count("EXAMPLE"))
        assert example_count >= 5, f"Only found {example_count} example mentions, expected at least 5"

    def test_professional_tone(self):
        """Prompt should maintain professional tone (no slang, no casual language)."""
        # Should not contain overly casual phrases
        casual_phrases = ["gonna", "wanna", "gotta", "kinda", "sorta"]
        for phrase in casual_phrases:
            assert phrase not in RAG_SYSTEM_PROMPT.lower(), f"Found casual phrase: {phrase}"

