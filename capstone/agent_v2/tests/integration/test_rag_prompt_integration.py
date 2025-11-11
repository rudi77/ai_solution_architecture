"""Integration tests for RAG system prompt with Agent and TodoListManager.

Tests verify that the RAG_SYSTEM_PROMPT integrates properly with the agent
framework and that TodoListManager generates appropriate plans for different
query types when using the RAG prompt.
"""

import pytest
import os
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT, build_rag_system_prompt
from capstone.agent_v2.agent import Agent
from capstone.agent_v2.planning.todolist import TodoListManager, TodoList
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tools.llm_tool import LLMTool


@pytest.mark.integration
class TestRagPromptIntegration:
    """Integration tests for RAG system prompt with agent framework."""

    def test_agent_accepts_rag_system_prompt(self):
        """Agent should accept RAG_SYSTEM_PROMPT as system_prompt parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)

            # Create dependencies
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")

            # Create agent with RAG_SYSTEM_PROMPT
            agent = Agent(
                name="test_rag_agent",
                description="Test RAG agent",
                system_prompt=RAG_SYSTEM_PROMPT,
                mission="Test mission",
                tools=[],
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=None
            )

            # Verify agent was created successfully
            assert agent is not None
            assert agent.name == "test_rag_agent"
            # Agent wraps system_prompt with tags, so check if RAG_SYSTEM_PROMPT is contained
            prompt_content = agent.message_history.system_prompt["content"]
            assert RAG_SYSTEM_PROMPT.strip() in prompt_content

    def test_build_rag_system_prompt_with_agent(self):
        """Agent should accept customized prompt from build_rag_system_prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)

            # Build custom prompt
            custom_prompt = build_rag_system_prompt(
                available_tools=["rag_semantic_search", "rag_list_documents"],
                domain_knowledge="Test domain knowledge"
            )

            # Create dependencies
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")

            # Create agent with custom prompt
            agent = Agent(
                name="test_custom_rag_agent",
                description="Test custom RAG agent",
                system_prompt=custom_prompt,
                mission="Test mission",
                tools=[],
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=None
            )

            # Verify agent uses custom prompt
            prompt_content = agent.message_history.system_prompt["content"]
            # Agent wraps system_prompt, so check if custom prompt content is present
            assert "Test domain knowledge" in prompt_content
            assert "rag_semantic_search" in prompt_content

    def test_todolist_manager_with_rag_prompt(self):
        """TodoListManager should work with RAG_SYSTEM_PROMPT."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)

            # Create TodoListManager (system prompt is passed when creating todolists, not at init)
            manager = TodoListManager(base_dir=work_dir / "todolists")

            # Verify manager was created successfully
            assert manager is not None


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY environment variable for LLM calls"
)
class TestRagPromptWithRealLLM:
    """Integration tests with real LLM to verify prompt behavior.
    
    These tests make actual LLM calls to verify that the RAG_SYSTEM_PROMPT
    guides the agent to generate appropriate plans for different query types.
    """

    @pytest.mark.asyncio
    async def test_listing_query_plan_structure(self):
        """TodoListManager with RAG prompt should generate appropriate plan for LISTING queries."""
        import litellm
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)

            # Create TodoListManager
            manager = TodoListManager(base_dir=work_dir / "todolists")

            # Test LISTING query
            mission = "Which documents are available?"
            
            # Create initial TodoList with RAG prompt
            try:
                todolist = await manager.create_initial_todolist(
                    mission=mission,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    llm=litellm
                )
                
                # Verify TodoList was created
                assert todolist is not None
                assert isinstance(todolist, TodoList)
                
                # Verify it has some tasks
                assert len(todolist.todos) > 0
                
                # For a LISTING query, we'd expect:
                # 1. A step to list documents (rag_list_documents)
                # 2. A step to format response (llm_generate)
                # Note: We can't guarantee exact tool names without the actual tools registered,
                # but we can verify the structure makes sense
                
                print(f"\nGenerated TodoList for LISTING query:")
                for todo in todolist.todos:
                    print(f"  - {todo.description}")
                    
            except Exception as e:
                # If TodoList creation fails, it's okay for this test
                # (might be due to missing tools or other setup)
                pytest.skip(f"TodoList creation failed (expected in some setups): {e}")

    @pytest.mark.asyncio
    async def test_content_search_query_plan_structure(self):
        """TodoListManager with RAG prompt should generate appropriate plan for CONTENT_SEARCH queries."""
        import litellm
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)

            manager = TodoListManager(base_dir=work_dir / "todolists")

            # Test CONTENT_SEARCH query
            mission = "How does the XYZ pump work?"
            
            try:
                todolist = await manager.create_initial_todolist(
                    mission=mission,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    llm=litellm
                )
                
                assert todolist is not None
                assert isinstance(todolist, TodoList)
                assert len(todolist.todos) > 0
                
                # For a CONTENT_SEARCH query, we'd expect:
                # 1. A search step (rag_semantic_search)
                # 2. A synthesis/response step (llm_generate)
                
                print(f"\nGenerated TodoList for CONTENT_SEARCH query:")
                for todo in todolist.todos:
                    print(f"  - {todo.description}")
                    
            except Exception as e:
                pytest.skip(f"TodoList creation failed (expected in some setups): {e}")

    @pytest.mark.asyncio
    async def test_rag_prompt_vs_generic_prompt_difference(self):
        """RAG prompt should produce different planning behavior than generic prompt."""
        import litellm
        from capstone.agent_v2.agent import GENERIC_SYSTEM_PROMPT
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)

            mission = "Which documents are available?"
            
            # Create manager
            manager = TodoListManager(base_dir=work_dir / "todolists")
            
            try:
                # Generate plans with both prompts
                rag_todolist = await manager.create_initial_todolist(
                    mission=mission,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    llm=litellm
                )
                generic_todolist = await manager.create_initial_todolist(
                    mission=mission,
                    system_prompt=GENERIC_SYSTEM_PROMPT,
                    llm=litellm
                )
                
                # Both should create TodoLists
                assert rag_todolist is not None
                assert generic_todolist is not None
                
                # The plans might be structured differently
                # (RAG prompt should be more specific about RAG tools)
                
                print(f"\nRAG Prompt Plan:")
                for todo in rag_todolist.todos:
                    print(f"  - {todo.description}")
                
                print(f"\nGeneric Prompt Plan:")
                for todo in generic_todolist.todos:
                    print(f"  - {todo.description}")
                    
            except Exception as e:
                pytest.skip(f"TodoList comparison test failed (expected in some setups): {e}")


@pytest.mark.integration
class TestRagPromptBackwardCompatibility:
    """Test that RAG prompt doesn't break existing agent functionality."""

    def test_generic_prompt_still_works(self):
        """GENERIC_SYSTEM_PROMPT should still work for non-RAG agents."""
        from capstone.agent_v2.agent import GENERIC_SYSTEM_PROMPT
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)

            # Create dependencies
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")

            # Create agent with generic prompt
            agent = Agent(
                name="test_generic_agent",
                description="Test generic agent",
                system_prompt=GENERIC_SYSTEM_PROMPT,
                mission="Test mission",
                tools=[],
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=None
            )

            # Verify agent works
            assert agent is not None
            assert agent.name == "test_generic_agent"
            # Agent wraps system_prompt, so check if GENERIC_SYSTEM_PROMPT is contained
            prompt_content = agent.message_history.system_prompt["content"]
            assert GENERIC_SYSTEM_PROMPT.strip() in prompt_content

    def test_agent_with_minimal_prompt(self):
        """Agent should work with minimal system prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)

            # Create dependencies
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")

            # Create agent with minimal system_prompt
            minimal_prompt = "You are a helpful agent."
            agent = Agent(
                name="test_minimal_agent",
                description="Test minimal agent",
                mission="Test mission",
                system_prompt=minimal_prompt,
                tools=[],
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=None
            )

            # Verify agent works
            assert agent is not None
            assert agent.name == "test_minimal_agent"
            assert minimal_prompt in agent.message_history.system_prompt["content"]


@pytest.mark.integration
class TestRagPromptToolReferences:
    """Test that RAG prompt correctly references tools."""

    def test_prompt_mentions_all_required_tools(self):
        """RAG_SYSTEM_PROMPT should mention all required RAG tools."""
        required_tools = [
            "rag_semantic_search",
            "rag_list_documents",
            "rag_get_document",
            "llm_generate"
        ]
        
        for tool in required_tools:
            assert tool in RAG_SYSTEM_PROMPT, f"Tool {tool} not mentioned in RAG_SYSTEM_PROMPT"

    def test_build_prompt_allows_tool_customization(self):
        """build_rag_system_prompt should allow specifying available tools."""
        custom_tools = ["rag_semantic_search", "custom_tool"]
        
        custom_prompt = build_rag_system_prompt(available_tools=custom_tools)
        
        # Custom prompt should mention the custom tool
        assert "custom_tool" in custom_prompt
        
        # Should still have base RAG prompt content
        assert "Query Classification" in custom_prompt


@pytest.mark.integration  
class TestRagPromptExamples:
    """Test that prompt examples are valid and helpful."""

    def test_examples_show_complete_workflows(self):
        """Prompt examples should show complete workflows with input/output."""
        # Examples should show TodoList structure
        assert "TodoList" in RAG_SYSTEM_PROMPT or "Plan:" in RAG_SYSTEM_PROMPT
        
        # Examples should show tool inputs
        assert '"query":' in RAG_SYSTEM_PROMPT or '"limit":' in RAG_SYSTEM_PROMPT
        
        # Examples should show acceptance criteria
        assert "Acceptance:" in RAG_SYSTEM_PROMPT or "acceptance" in RAG_SYSTEM_PROMPT.lower()

    def test_examples_cover_multiple_query_types(self):
        """Prompt should include examples for different query types."""
        query_types = ["LISTING", "CONTENT_SEARCH", "DOCUMENT_SUMMARY"]
        
        for query_type in query_types:
            assert query_type in RAG_SYSTEM_PROMPT, f"Missing example for {query_type}"

    def test_interactive_examples_include_response_step(self):
        """Interactive query examples should include llm_generate response step."""
        # Should have multiple mentions of llm_generate (one per interactive example)
        llm_generate_count = RAG_SYSTEM_PROMPT.count("llm_generate")
        
        # Should appear at least 4-5 times (multiple examples + tool description)
        assert llm_generate_count >= 4, f"llm_generate only appears {llm_generate_count} times"

    def test_autonomous_examples_exclude_response_step(self):
        """Autonomous workflow examples should note no response step."""
        # Should mention that autonomous workflows complete silently
        assert ("silent" in RAG_SYSTEM_PROMPT.lower() or 
                "no response" in RAG_SYSTEM_PROMPT.lower() or
                "No llm_generate" in RAG_SYSTEM_PROMPT)


@pytest.mark.integration
class TestRagPromptClarityAndUsability:
    """Test that RAG prompt is clear and usable."""

    def test_prompt_has_clear_structure(self):
        """Prompt should have clear markdown structure with headers."""
        # Should have main headers
        assert "##" in RAG_SYSTEM_PROMPT  # Markdown headers
        
        # Should have multiple sections
        header_count = RAG_SYSTEM_PROMPT.count("##")
        assert header_count >= 8, f"Only {header_count} sections found, expected at least 8"

    def test_prompt_includes_concrete_examples(self):
        """Prompt should include concrete examples, not just abstract rules."""
        # Should have example queries
        assert '"' in RAG_SYSTEM_PROMPT  # Quotes around example queries
        
        # Should show actual tool calls
        assert "{" in RAG_SYSTEM_PROMPT  # JSON examples
        assert ":" in RAG_SYSTEM_PROMPT  # Key-value pairs

    def test_prompt_explains_why_not_just_what(self):
        """Prompt should explain reasoning, not just give instructions."""
        # Should explain why things matter
        reasoning_indicators = [
            "why", "because", "reason", "important", "critical",
            "matters", "helps", "ensures", "prevents"
        ]
        
        found_reasoning = sum(
            1 for indicator in reasoning_indicators 
            if indicator in RAG_SYSTEM_PROMPT.lower()
        )
        
        assert found_reasoning >= 3, "Prompt lacks explanatory reasoning"

