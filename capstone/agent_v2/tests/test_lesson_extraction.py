"""Tests for lesson extraction (Story 4.2)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from capstone.agent_v2.planning.todolist import TodoItem, TaskStatus
from memory.memory_manager import SkillMemory


class TestLessonExtractionPatterns:
    """Test learning pattern detection heuristics."""
    
    def test_pattern_multiple_attempts(self):
        """Test detection of multiple attempts pattern."""
        from capstone.agent_v2.agent import Agent
        
        # Create mock agent
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Step with multiple attempts and success
        step = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Must succeed",
            status=TaskStatus.COMPLETED,
            attempts=3
        )
        
        assert agent._has_learning_pattern(step) is True
    
    def test_pattern_replanning(self):
        """Test detection of replanning pattern."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Step with replanning and success
        step = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Must succeed",
            status=TaskStatus.COMPLETED,
            replan_count=1
        )
        
        assert agent._has_learning_pattern(step) is True
    
    def test_pattern_tool_substitution(self):
        """Test detection of tool substitution pattern."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Step with different tools used
        step = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Must succeed",
            status=TaskStatus.COMPLETED,
            execution_history=[
                {"tool": "PythonTool", "success": False, "error": "ModuleNotFound"},
                {"tool": "PowerShellTool", "success": True, "error": None}
            ]
        )
        
        assert agent._has_learning_pattern(step) is True
    
    def test_pattern_error_recovery(self):
        """Test detection of error recovery pattern."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Step with errors but eventual success
        step = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Must succeed",
            status=TaskStatus.COMPLETED,
            execution_history=[
                {"tool": "PythonTool", "success": False, "error": "SyntaxError"},
                {"tool": "PythonTool", "success": True, "error": None}
            ]
        )
        
        assert agent._has_learning_pattern(step) is True
    
    def test_no_pattern_single_success(self):
        """Test no pattern for straightforward success."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Step with single successful attempt
        step = TodoItem(
            position=1,
            description="Test task",
            acceptance_criteria="Must succeed",
            status=TaskStatus.COMPLETED,
            attempts=1,
            replan_count=0,
            execution_history=[
                {"tool": "PythonTool", "success": True, "error": None}
            ]
        )
        
        assert agent._has_learning_pattern(step) is False


class TestExecutionContextBuilder:
    """Test building execution context for lesson extraction."""
    
    def test_build_context_basic(self):
        """Test building context from TodoItem."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        
        step = TodoItem(
            position=1,
            description="Install Python package",
            acceptance_criteria="Package installed",
            execution_history=[
                {"tool": "PythonTool", "success": False, "error": "ModuleNotFoundError"},
                {"tool": "PowerShellTool", "success": True, "error": None}
            ],
            execution_result={"success": True, "output": "Package installed"}
        )
        
        context = agent._build_execution_context(step)
        
        assert context["task_description"] == "Install Python package"
        assert context["attempt_count"] == 2
        assert "ModuleNotFoundError" in context["initial_error"]
        assert "PythonTool" in context["tools_used"]
        assert "PowerShellTool" in context["tools_used"]
    
    def test_build_context_no_initial_error(self):
        """Test context building when no initial error."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        
        step = TodoItem(
            position=1,
            description="Simple task",
            acceptance_criteria="Done",
            execution_history=[],
            execution_result={"success": True}
        )
        
        context = agent._build_execution_context(step)
        
        assert context["initial_error"] == "N/A"
        assert context["attempt_count"] == 0


class TestLessonExtraction:
    """Test lesson extraction with LLM."""
    
    @pytest.mark.asyncio
    async def test_extract_lesson_success(self):
        """Test successful lesson extraction."""
        from capstone.agent_v2.agent import Agent
        from capstone.agent_v2.services.llm_service import LLMService
        
        # Mock LLM service
        llm_service = AsyncMock(spec=LLMService)
        llm_service.complete = AsyncMock(return_value='{"context": "Python module installation", "what_failed": "PythonTool failed with ModuleNotFoundError", "what_worked": "PowerShellTool with pip install succeeded", "lesson": "Use system package manager when Python module missing", "tool_name": "PowerShellTool", "confidence": 0.9}')
        
        # Create agent with mocked LLM
        agent = MagicMock(spec=Agent)
        agent.llm_service = llm_service
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        agent._extract_lesson = Agent._extract_lesson.__get__(agent)
        
        step = TodoItem(
            position=1,
            description="Install package",
            acceptance_criteria="Package installed",
            execution_history=[
                {"tool": "PythonTool", "success": False, "error": "ModuleNotFoundError"},
                {"tool": "PowerShellTool", "success": True, "error": None}
            ],
            execution_result={"success": True}
        )
        
        lesson = await agent._extract_lesson(step)
        
        assert lesson is not None
        assert isinstance(lesson, SkillMemory)
        assert "Python module installation" in lesson.context
        assert "PowerShellTool" in lesson.lesson
    
    @pytest.mark.asyncio
    async def test_extract_lesson_low_confidence(self):
        """Test lesson extraction with low confidence returns None."""
        from capstone.agent_v2.agent import Agent
        from capstone.agent_v2.services.llm_service import LLMService
        
        llm_service = AsyncMock(spec=LLMService)
        llm_service.complete = AsyncMock(return_value='{"context": "Unclear situation", "what_failed": "Unknown", "what_worked": "Maybe something", "lesson": "Not sure", "tool_name": null, "confidence": 0.3}')
        
        agent = MagicMock(spec=Agent)
        agent.llm_service = llm_service
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        agent._extract_lesson = Agent._extract_lesson.__get__(agent)
        agent.logger = MagicMock()
        
        step = TodoItem(
            position=1,
            description="Unclear task",
            acceptance_criteria="Done",
            execution_history=[
                {"tool": "SomeTool", "success": False, "error": "Error"},
                {"tool": "SomeTool", "success": True, "error": None}
            ],
            execution_result={"success": True}
        )
        
        lesson = await agent._extract_lesson(step)
        
        assert lesson is None
    
    @pytest.mark.asyncio
    async def test_extract_lesson_timeout(self):
        """Test lesson extraction timeout handling."""
        from capstone.agent_v2.agent import Agent
        from capstone.agent_v2.services.llm_service import LLMService
        
        llm_service = AsyncMock(spec=LLMService)
        # Simulate timeout
        async def slow_complete(*args, **kwargs):
            await asyncio.sleep(10)
            return "{}"
        llm_service.complete = slow_complete
        
        agent = MagicMock(spec=Agent)
        agent.llm_service = llm_service
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        agent._extract_lesson = Agent._extract_lesson.__get__(agent)
        agent.logger = MagicMock()
        
        step = TodoItem(
            position=1,
            description="Task",
            acceptance_criteria="Done",
            execution_history=[],
            execution_result={"success": True}
        )
        
        lesson = await agent._extract_lesson(step)
        
        assert lesson is None
    
    @pytest.mark.asyncio
    async def test_extract_lesson_llm_error(self):
        """Test lesson extraction handles LLM errors gracefully."""
        from capstone.agent_v2.agent import Agent
        from capstone.agent_v2.services.llm_service import LLMService
        
        llm_service = AsyncMock(spec=LLMService)
        llm_service.complete = AsyncMock(side_effect=Exception("LLM API error"))
        
        agent = MagicMock(spec=Agent)
        agent.llm_service = llm_service
        agent._build_execution_context = Agent._build_execution_context.__get__(agent)
        agent._extract_lesson = Agent._extract_lesson.__get__(agent)
        agent.logger = MagicMock()
        
        step = TodoItem(
            position=1,
            description="Task",
            acceptance_criteria="Done",
            execution_history=[],
            execution_result={"success": True}
        )
        
        lesson = await agent._extract_lesson(step)
        
        assert lesson is None


@pytest.mark.integration
class TestLessonExtractionIntegration:
    """Integration tests for lesson extraction in full agent execution."""
    
    @pytest.mark.asyncio
    async def test_lesson_stored_after_completion(self):
        """Test that lesson is extracted and stored after task completion."""
        from capstone.agent_v2.agent import Agent
        from capstone.agent_v2.planning.todolist import TodoListManager
        from capstone.agent_v2.statemanager import StateManager
        from capstone.agent_v2.services.llm_service import LLMService
        from memory.memory_manager import MemoryManager
        import tempfile
        
        # Create temp directories
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock LLM service
            llm_service = AsyncMock(spec=LLMService)
            
            # Create memory manager
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # Create agent components
            planner = MagicMock(spec=TodoListManager)
            state_manager = MagicMock(spec=StateManager)
            
            # Create agent with memory
            agent = Agent(
                name="test",
                description="test",
                system_prompt="test",
                mission="test",
                tools=[],
                todo_list_manager=planner,
                state_manager=state_manager,
                llm_service=llm_service,
                memory_manager=memory_manager,
                enable_lesson_extraction=True
            )
            
            # Mock lesson extraction to return a valid lesson
            async def mock_extract(step):
                return SkillMemory(
                    context="Test context",
                    lesson="Test lesson",
                    tool_name="TestTool"
                )
            
            agent._extract_lesson = mock_extract
            
            # Create a step with learning pattern
            step = TodoItem(
                position=1,
                description="Test task",
                acceptance_criteria="Done",
                status=TaskStatus.COMPLETED,
                attempts=2,
                execution_history=[
                    {"tool": "Tool1", "success": False, "error": "Error"},
                    {"tool": "Tool2", "success": True, "error": None}
                ]
            )
            
            # Test that pattern is detected
            assert agent._has_learning_pattern(step) is True
            
            # Extract and store lesson
            lesson = await agent._extract_lesson(step)
            if lesson:
                await memory_manager.store_memory(lesson)
            
            # Verify lesson was stored
            all_memories = await memory_manager.list_all_memories()
            assert len(all_memories) == 1
            assert all_memories[0].context == "Test context"

