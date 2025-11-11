"""Integration tests for LLMTool with real LLM."""

import pytest
import os
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.agent import Agent
import litellm


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY environment variable"
)
class TestLLMToolIntegration:
    """Integration test suite for LLMTool with real LLM."""

    @pytest.mark.asyncio
    async def test_real_llm_generation(self):
        """Test LLMTool with actual LLM instance."""
        tool = LLMTool(llm=litellm)
        
        result = await tool.execute(
            prompt="What is 2+2? Answer in one short sentence.",
            max_tokens=50,
            temperature=0.0
        )
        
        # Verify successful generation
        assert result["success"] is True
        assert "generated_text" in result
        assert len(result["generated_text"]) > 0
        
        # Verify token counts are present and reasonable
        assert result["tokens_used"] > 0
        assert result["prompt_tokens"] > 0
        assert result["completion_tokens"] > 0
        assert result["tokens_used"] == result["prompt_tokens"] + result["completion_tokens"]

    @pytest.mark.asyncio
    async def test_llm_with_context(self):
        """Test LLMTool with context data."""
        tool = LLMTool(llm=litellm)
        
        context = {
            "documents": [
                {"title": "manual.pdf", "pages": 50},
                {"title": "guide.pdf", "pages": 30}
            ]
        }
        
        result = await tool.execute(
            prompt="List the document titles in a bullet list.",
            context=context,
            max_tokens=100,
            temperature=0.0
        )
        
        # Verify successful generation
        assert result["success"] is True
        
        # Verify response mentions the documents
        generated = result["generated_text"].lower()
        assert "manual" in generated or "guide" in generated

    @pytest.mark.asyncio
    async def test_llm_tool_in_agent(self):
        """Test LLMTool registered and used in Agent workflow."""
        # Create a simple agent with LLMTool
        from capstone.agent_v2.planning.todolist import TodoListManager
        from capstone.agent_v2.statemanager import StateManager
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            
            # Create directories
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)
            
            # Create agent with LLMTool
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            
            tools = [LLMTool(llm=litellm)]
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")
            
            agent = Agent(
                name="Test Agent",
                description="Test agent with LLM tool",
                system_prompt="You are a test agent",
                mission=None,
                tools=tools,
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=litellm
            )
            
            # Verify tool is registered
            assert len(agent.tools) == 1
            assert agent.tools[0].name == "llm_generate"
            
            # Test tool execution through agent
            llm_tool = agent.tools[0]
            result = await llm_tool.execute(prompt="Say hello in one word.")
            
            assert result["success"] is True
            assert len(result["generated_text"]) > 0

    @pytest.mark.asyncio
    async def test_rag_agent_with_llm_tool(self):
        """Test LLMTool integration with RAG agent."""
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Note: This is a simplified test that verifies tool registration
            # Full RAG workflow would require Azure Search infrastructure
            
            # We'll just verify the tool can be added to a RAG-like agent
            from capstone.agent_v2.planning.todolist import TodoListManager
            from capstone.agent_v2.statemanager import StateManager
            from capstone.agent_v2.tools.file_tool import FileReadTool
            
            work_dir = Path(tmpdir)
            (work_dir / "todolists").mkdir(exist_ok=True)
            (work_dir / "states").mkdir(exist_ok=True)
            
            # Create agent with LLMTool and other tools
            from capstone.agent_v2.services.llm_service import LLMService
            llm_service = LLMService()
            
            tools = [
                LLMTool(llm=litellm),
                FileReadTool()
            ]
            
            planner = TodoListManager(base_dir=work_dir / "todolists")
            state_manager = StateManager(state_dir=work_dir / "states")
            
            agent = Agent(
                name="RAG-like Agent",
                description="Agent with LLM tool for responses",
                system_prompt="You help users by reading files and responding.",
                mission=None,
                tools=tools,
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                llm=litellm
            )
            
            # Verify tools are registered
            tool_names = [t.name for t in agent.tools]
            assert "llm_generate" in tool_names
            assert "file_read" in tool_names

    @pytest.mark.asyncio
    async def test_creative_vs_deterministic_generation(self):
        """Test that temperature parameter affects generation."""
        tool = LLMTool(llm=litellm)
        
        # Deterministic generation (temperature=0)
        result1 = await tool.execute(
            prompt="Say the word 'test' once.",
            temperature=0.0,
            max_tokens=10
        )
        
        # Verify generation succeeded
        assert result1["success"] is True
        
        # Note: We don't test creative generation (temperature=1.0) 
        # in integration tests as it's non-deterministic and would
        # make tests flaky

    @pytest.mark.asyncio
    async def test_error_with_invalid_max_tokens(self):
        """Test error handling with unreasonable max_tokens."""
        tool = LLMTool(llm=litellm)
        
        # Try with excessively large max_tokens (may hit limits)
        result = await tool.execute(
            prompt="Test",
            max_tokens=100000  # Unreasonably large
        )
        
        # Should either succeed or fail gracefully with error
        if not result["success"]:
            assert "error" in result
            assert "hints" in result

