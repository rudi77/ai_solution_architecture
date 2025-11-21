"""Integration tests for the complete memory system (Stories 4.1, 4.2, 4.3)."""

import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from memory.memory_manager import MemoryManager, SkillMemory
from capstone.agent_v2.planning.todolist import TodoItem, TodoList, TodoListManager, TaskStatus


@pytest.mark.integration
class TestCompleteMemoryFlow:
    """Test complete memory system flow from lesson extraction to retrieval."""
    
    @pytest.mark.asyncio
    async def test_memory_lifecycle(self):
        """Test full memory lifecycle: extract → store → retrieve → success tracking."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create memory manager
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # 1. Store a memory (simulating lesson extraction)
            memory = SkillMemory(
                context="Python tool failed with ModuleNotFoundError",
                lesson="Use PowerShellTool to install packages when Python import fails",
                tool_name="PowerShellTool"
            )
            
            result = await memory_manager.store_memory(memory)
            assert result is True
            
            # 2. Retrieve memories for similar mission
            retrieved = await memory_manager.retrieve_relevant_memories(
                query="Install Python package that's missing",
                top_k=5,
                min_similarity=0.0  # Low threshold for test
            )
            
            # Should find at least one memory
            assert len(retrieved) > 0
            
            # 3. Simulate success tracking
            for mem in retrieved:
                await memory_manager.update_success_count(mem.id, increment=1)
            
            # 4. Verify success count updated
            all_memories = await memory_manager.list_all_memories()
            assert any(m.success_count > 0 for m in all_memories)
    
    @pytest.mark.asyncio
    async def test_memory_in_planning(self):
        """Test memory retrieval integration in TodoListManager."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create memory manager with test memories
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # Store a relevant memory
            memory = SkillMemory(
                context="Git operations require authentication",
                lesson="Always check if GITHUB_TOKEN is set before git operations",
                tool_name="GitTool"
            )
            await memory_manager.store_memory(memory)
            
            # Mock LLM service
            llm_service = AsyncMock()
            llm_service.complete = AsyncMock(return_value={
                "success": True,
                "content": '{"items": [{"position": 1, "description": "Test", "acceptance_criteria": "Done", "dependencies": [], "status": "PENDING"}], "open_questions": [], "notes": ""}',
                "usage": {"total_tokens": 100}
            })
            
            # Create TodoListManager
            planner = TodoListManager(
                base_dir=f"{tmpdir}/todolists",
                llm_service=llm_service
            )
            
            # Create todolist with memory retrieval
            todolist = await planner.create_todolist(
                mission="Create a new Git repository",
                tools_desc="GitTool: Creates git repositories",
                answers={},
                memory_manager=memory_manager
            )
            
            # Verify todolist created
            assert todolist is not None
            assert len(todolist.items) > 0
            
            # Verify memories were retrieved
            assert hasattr(todolist, 'retrieved_memories')
            assert len(todolist.retrieved_memories) > 0
    
    @pytest.mark.asyncio
    async def test_lesson_extraction_pattern_detection(self):
        """Test that learning patterns are correctly detected."""
        from capstone.agent_v2.agent import Agent
        
        agent = MagicMock(spec=Agent)
        agent._has_learning_pattern = Agent._has_learning_pattern.__get__(agent)
        
        # Test various learning patterns
        test_cases = [
            {
                "name": "Multiple attempts",
                "step": TodoItem(
                    position=1,
                    description="Task",
                    acceptance_criteria="Done",
                    status=TaskStatus.COMPLETED,
                    attempts=3
                ),
                "expected": True
            },
            {
                "name": "Tool substitution",
                "step": TodoItem(
                    position=1,
                    description="Task",
                    acceptance_criteria="Done",
                    status=TaskStatus.COMPLETED,
                    execution_history=[
                        {"tool": "Tool1", "success": False, "error": "Error"},
                        {"tool": "Tool2", "success": True, "error": None}
                    ]
                ),
                "expected": True
            },
            {
                "name": "Single success",
                "step": TodoItem(
                    position=1,
                    description="Task",
                    acceptance_criteria="Done",
                    status=TaskStatus.COMPLETED,
                    attempts=1,
                    execution_history=[
                        {"tool": "Tool1", "success": True, "error": None}
                    ]
                ),
                "expected": False
            }
        ]
        
        for test_case in test_cases:
            result = agent._has_learning_pattern(test_case["step"])
            assert result == test_case["expected"], f"Failed for: {test_case['name']}"
    
    @pytest.mark.asyncio
    async def test_memory_success_tracking_flow(self):
        """Test that memories are tracked for success when planning helps."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # Store memories
            memories = [
                SkillMemory(
                    context="Context 1",
                    lesson="Lesson 1",
                    tool_name="Tool1"
                ),
                SkillMemory(
                    context="Context 2",
                    lesson="Lesson 2",
                    tool_name="Tool2"
                )
            ]
            
            for mem in memories:
                await memory_manager.store_memory(mem)
            
            # Retrieve memories
            retrieved = await memory_manager.retrieve_relevant_memories(
                query="Similar context",
                top_k=5
            )
            
            assert len(retrieved) > 0
            
            # Simulate successful execution with these memories
            for mem in retrieved:
                # Initial success count should be 0
                all_mems = await memory_manager.list_all_memories()
                current_mem = next(m for m in all_mems if m.id == mem.id)
                initial_count = current_mem.success_count
                
                # Update success count
                await memory_manager.update_success_count(mem.id, increment=1)
                
                # Verify incremented
                all_mems = await memory_manager.list_all_memories()
                current_mem = next(m for m in all_mems if m.id == mem.id)
                assert current_mem.success_count == initial_count + 1


@pytest.mark.integration
class TestMemoryPruning:
    """Test memory pruning functionality."""
    
    @pytest.mark.asyncio
    async def test_prune_stale_memories_integration(self):
        """Test pruning of stale memories."""
        from datetime import datetime, timedelta
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # Create old memory
            old_date = (datetime.now() - timedelta(days=100)).isoformat()
            old_memory = SkillMemory(
                context="Old memory",
                lesson="Should be pruned",
                created_at=old_date,
                last_used=old_date
            )
            
            await memory_manager.store_memory(old_memory)
            
            # Verify stored
            all_memories = await memory_manager.list_all_memories()
            assert len(all_memories) == 1
            
            # Prune
            count = await memory_manager.prune_stale_memories()
            assert count == 1
            
            # Verify removed
            all_memories = await memory_manager.list_all_memories()
            assert len(all_memories) == 0


@pytest.mark.performance
class TestMemoryPerformance:
    """Performance tests for memory retrieval."""
    
    @pytest.mark.asyncio
    async def test_retrieval_performance(self):
        """Test that retrieval is fast enough for production use."""
        import time
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_manager = MemoryManager(
                memory_dir=f"{tmpdir}/memory",
                enable_memory=True,
                auto_prune=False
            )
            
            # Store multiple memories
            with patch.object(memory_manager, '_generate_embedding', return_value=[0.1] * 1536):
                for i in range(50):
                    memory = SkillMemory(
                        context=f"Context {i}",
                        lesson=f"Lesson {i}"
                    )
                    await memory_manager.store_memory(memory)
            
            # Measure retrieval time
            start = time.time()
            results = await memory_manager.retrieve_relevant_memories(
                query="Test query",
                top_k=5
            )
            elapsed = (time.time() - start) * 1000
            
            # Should be fast (<200ms)
            assert elapsed < 200, f"Retrieval took {elapsed}ms"
            assert len(results) <= 5

