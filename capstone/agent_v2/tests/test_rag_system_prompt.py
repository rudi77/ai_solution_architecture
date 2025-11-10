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

    def test_has_query_classification_section(self):
        """Prompt should include Query Classification section."""
        assert "## Query Classification" in RAG_SYSTEM_PROMPT
        # Should mention classification concepts
        assert "classify" in RAG_SYSTEM_PROMPT.lower() or "classification" in RAG_SYSTEM_PROMPT.lower()

    def test_has_planning_patterns_section(self):
        """Prompt should include Planning Patterns section."""
        assert "## Planning Patterns" in RAG_SYSTEM_PROMPT
        # Should mention TodoList or planning
        assert "todolist" in RAG_SYSTEM_PROMPT.lower() or "plan" in RAG_SYSTEM_PROMPT.lower()

    def test_has_tool_usage_rules_section(self):
        """Prompt should include Tool Usage Rules section."""
        assert "## Tool Usage Rules" in RAG_SYSTEM_PROMPT
        # Should mention tools
        assert "tool" in RAG_SYSTEM_PROMPT.lower()

    def test_has_response_generation_guidelines_section(self):
        """Prompt should include Response Generation Guidelines section."""
        assert "## Response Generation Guidelines" in RAG_SYSTEM_PROMPT or "Response Generation" in RAG_SYSTEM_PROMPT
        # Should mention interactive and autonomous
        assert "interactive" in RAG_SYSTEM_PROMPT.lower()
        assert "autonomous" in RAG_SYSTEM_PROMPT.lower()

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


class TestQueryClassificationCategories:
    """Test that all required query classification categories are defined."""

    def test_has_listing_category(self):
        """Prompt should define LISTING query category."""
        assert "LISTING" in RAG_SYSTEM_PROMPT
        # Should have examples for listing
        assert "documents are available" in RAG_SYSTEM_PROMPT or "Which documents" in RAG_SYSTEM_PROMPT

    def test_has_content_search_category(self):
        """Prompt should define CONTENT_SEARCH query category."""
        assert "CONTENT_SEARCH" in RAG_SYSTEM_PROMPT
        # Should mention content within documents
        assert "content" in RAG_SYSTEM_PROMPT.lower()

    def test_has_document_summary_category(self):
        """Prompt should define DOCUMENT_SUMMARY query category."""
        assert "DOCUMENT_SUMMARY" in RAG_SYSTEM_PROMPT
        # Should mention summary
        assert "summary" in RAG_SYSTEM_PROMPT.lower() or "summarize" in RAG_SYSTEM_PROMPT.lower()

    def test_has_metadata_search_category(self):
        """Prompt should define METADATA_SEARCH query category."""
        assert "METADATA_SEARCH" in RAG_SYSTEM_PROMPT
        # Should mention metadata or filtering
        assert "metadata" in RAG_SYSTEM_PROMPT.lower() or "filter" in RAG_SYSTEM_PROMPT.lower()

    def test_has_comparison_category(self):
        """Prompt should define COMPARISON query category."""
        assert "COMPARISON" in RAG_SYSTEM_PROMPT
        # Should mention comparing
        assert "compare" in RAG_SYSTEM_PROMPT.lower() or "comparison" in RAG_SYSTEM_PROMPT.lower()

    def test_categories_have_examples(self):
        """Each query category should have example queries."""
        # Should have multiple examples throughout
        assert RAG_SYSTEM_PROMPT.count("Example") >= 5 or RAG_SYSTEM_PROMPT.count("example") >= 5


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


class TestInteractiveVsAutonomousGuidance:
    """Test that prompt distinguishes interactive queries from autonomous workflows."""

    def test_explains_interactive_queries(self):
        """Prompt should explain interactive queries."""
        assert "interactive" in RAG_SYSTEM_PROMPT.lower()
        # Should mention user expects answer
        assert "answer" in RAG_SYSTEM_PROMPT.lower()

    def test_explains_autonomous_workflows(self):
        """Prompt should explain autonomous workflows."""
        assert "autonomous" in RAG_SYSTEM_PROMPT.lower()
        # Should mention silent/no response
        assert "silent" in RAG_SYSTEM_PROMPT.lower() or "no response" in RAG_SYSTEM_PROMPT.lower()

    def test_emphasizes_llm_generate_for_interactive(self):
        """Prompt should emphasize using llm_generate for interactive queries."""
        # Should have strong language about always including llm_generate
        assert "ALWAYS" in RAG_SYSTEM_PROMPT or "always" in RAG_SYSTEM_PROMPT.lower()
        # Should mention final step
        assert "final step" in RAG_SYSTEM_PROMPT.lower()


class TestPlanningPatternExamples:
    """Test that prompt includes concrete planning pattern examples."""

    def test_has_listing_example(self):
        """Prompt should include LISTING query example with TodoList."""
        assert "LISTING" in RAG_SYSTEM_PROMPT
        # Should show rag_list_documents usage
        assert "rag_list_documents" in RAG_SYSTEM_PROMPT

    def test_has_content_search_example(self):
        """Prompt should include CONTENT_SEARCH query example."""
        assert "CONTENT_SEARCH" in RAG_SYSTEM_PROMPT
        # Should show rag_semantic_search usage
        assert "rag_semantic_search" in RAG_SYSTEM_PROMPT

    def test_has_document_summary_example(self):
        """Prompt should include DOCUMENT_SUMMARY query example."""
        assert "DOCUMENT_SUMMARY" in RAG_SYSTEM_PROMPT
        # Should show multi-step process
        assert "rag_get_document" in RAG_SYSTEM_PROMPT

    def test_examples_include_acceptance_criteria(self):
        """Examples should show acceptance criteria."""
        # Should mention acceptance or expected outcome
        assert ("acceptance" in RAG_SYSTEM_PROMPT.lower() or 
                "expected outcome" in RAG_SYSTEM_PROMPT.lower() or
                "Acceptance:" in RAG_SYSTEM_PROMPT)

    def test_interactive_examples_include_llm_generate(self):
        """Interactive query examples should include llm_generate as final step."""
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
        assert "Query Classification" in result
        assert "Planning Patterns" in result
        assert "LISTING" in result


class TestPromptQuality:
    """Test overall quality aspects of the prompt."""

    def test_no_obvious_typos_in_headers(self):
        """Major section headers should be spelled correctly."""
        # Check for common section headers
        sections = [
            "Your Role", "Query Classification", "Planning Patterns",
            "Tool Usage", "Response Generation", "Clarification",
            "Multimodal"
        ]
        
        # At least most sections should be present
        found_sections = sum(1 for section in sections if section in RAG_SYSTEM_PROMPT)
        assert found_sections >= 6, f"Only found {found_sections} of expected {len(sections)} sections"

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

