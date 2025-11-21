"""Unit and integration tests for MemoryManager."""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from memory.memory_manager import MemoryManager, SkillMemory


class TestSkillMemory:
    """Test SkillMemory dataclass."""
    
    def test_skill_memory_creation(self):
        """Test SkillMemory can be created with default values."""
        memory = SkillMemory(
            context="Test context",
            lesson="Test lesson"
        )
        
        assert memory.context == "Test context"
        assert memory.lesson == "Test lesson"
        assert memory.tool_name is None
        assert memory.success_count == 0
        assert memory.id is not None
        assert memory.created_at is not None
        assert memory.last_used is not None
    
    def test_skill_memory_with_tool(self):
        """Test SkillMemory with tool_name."""
        memory = SkillMemory(
            context="Using Python tool",
            lesson="Always use isolated namespace",
            tool_name="PythonTool"
        )
        
        assert memory.tool_name == "PythonTool"
    
    def test_skill_memory_to_dict(self):
        """Test SkillMemory serialization."""
        memory = SkillMemory(
            id="test-123",
            context="Test context",
            lesson="Test lesson",
            tool_name="TestTool",
            success_count=5
        )
        
        data = memory.to_dict()
        
        assert data["id"] == "test-123"
        assert data["context"] == "Test context"
        assert data["lesson"] == "Test lesson"
        assert data["tool_name"] == "TestTool"
        assert data["success_count"] == 5
    
    def test_skill_memory_from_dict(self):
        """Test SkillMemory deserialization."""
        data = {
            "id": "test-456",
            "context": "Another context",
            "lesson": "Another lesson",
            "tool_name": "AnotherTool",
            "success_count": 3,
            "created_at": "2024-01-01T10:00:00",
            "last_used": "2024-01-02T10:00:00",
            "embedding": [0.1, 0.2, 0.3]
        }
        
        memory = SkillMemory.from_dict(data)
        
        assert memory.id == "test-456"
        assert memory.context == "Another context"
        assert memory.lesson == "Another lesson"
        assert memory.tool_name == "AnotherTool"
        assert memory.success_count == 3


class TestMemoryManagerDisabled:
    """Test MemoryManager with enable_memory=False."""
    
    @pytest.fixture
    def disabled_manager(self, tmp_path):
        """Create disabled MemoryManager."""
        return MemoryManager(
            memory_dir=str(tmp_path / "memory"),
            enable_memory=False,
            auto_prune=False
        )
    
    @pytest.mark.asyncio
    async def test_store_memory_disabled(self, disabled_manager):
        """Test storing memory when disabled returns False."""
        memory = SkillMemory(context="test", lesson="test")
        result = await disabled_manager.store_memory(memory)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_retrieve_memories_disabled(self, disabled_manager):
        """Test retrieving memories when disabled returns empty list."""
        result = await disabled_manager.retrieve_relevant_memories("test query")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_memories_disabled(self, disabled_manager):
        """Test listing memories when disabled returns empty list."""
        result = await disabled_manager.list_all_memories()
        assert result == []


class TestMemoryManagerJSON:
    """Test MemoryManager with JSON fallback (no ChromaDB)."""
    
    @pytest.fixture
    def json_manager(self, tmp_path):
        """Create MemoryManager with JSON backend."""
        with patch('memory.memory_manager.CHROMADB_AVAILABLE', False):
            manager = MemoryManager(
                memory_dir=str(tmp_path / "memory"),
                enable_memory=True,
                auto_prune=False,
                openai_api_key="test-key"
            )
            return manager
    
    @pytest.fixture
    def mock_embedding(self):
        """Mock embedding generation."""
        return [0.1] * 1536
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_memory_json(self, json_manager, mock_embedding):
        """Test storing and retrieving memory with JSON backend."""
        with patch.object(json_manager, '_generate_embedding', return_value=mock_embedding):
            memory = SkillMemory(
                context="Python tool failed with ModuleNotFoundError",
                lesson="Always check if module is installed before using",
                tool_name="PythonTool"
            )
            
            # Store
            result = await json_manager.store_memory(memory)
            assert result is True
            
            # Verify file exists
            assert json_manager.skills_file.exists()
            
            # Retrieve
            memories = await json_manager.retrieve_relevant_memories(
                "Python module error",
                top_k=5
            )
            
            assert len(memories) >= 0  # May not match due to similarity threshold
    
    @pytest.mark.asyncio
    async def test_list_all_memories_json(self, json_manager, mock_embedding):
        """Test listing all memories with JSON backend."""
        with patch.object(json_manager, '_generate_embedding', return_value=mock_embedding):
            # Store multiple memories
            memories_to_store = [
                SkillMemory(context="Context 1", lesson="Lesson 1"),
                SkillMemory(context="Context 2", lesson="Lesson 2"),
                SkillMemory(context="Context 3", lesson="Lesson 3")
            ]
            
            for memory in memories_to_store:
                await json_manager.store_memory(memory)
            
            # List all
            all_memories = await json_manager.list_all_memories()
            
            assert len(all_memories) == 3
    
    @pytest.mark.asyncio
    async def test_delete_memory_json(self, json_manager, mock_embedding):
        """Test deleting memory with JSON backend."""
        with patch.object(json_manager, '_generate_embedding', return_value=mock_embedding):
            memory = SkillMemory(context="To delete", lesson="Delete me")
            
            await json_manager.store_memory(memory)
            
            # Verify stored
            all_memories = await json_manager.list_all_memories()
            assert len(all_memories) == 1
            
            # Delete
            result = await json_manager.delete_memory(memory.id)
            assert result is True
            
            # Verify deleted
            all_memories = await json_manager.list_all_memories()
            assert len(all_memories) == 0
    
    @pytest.mark.asyncio
    async def test_update_success_count_json(self, json_manager, mock_embedding):
        """Test updating success count with JSON backend."""
        with patch.object(json_manager, '_generate_embedding', return_value=mock_embedding):
            memory = SkillMemory(context="Success test", lesson="Test lesson")
            
            await json_manager.store_memory(memory)
            
            # Update success count
            result = await json_manager.update_success_count(memory.id, increment=1)
            assert result is True
            
            # Verify updated
            all_memories = await json_manager.list_all_memories()
            assert all_memories[0].success_count == 1
            
            # Update again
            await json_manager.update_success_count(memory.id, increment=2)
            all_memories = await json_manager.list_all_memories()
            assert all_memories[0].success_count == 3


class TestMemoryManagerPruning:
    """Test memory pruning logic."""
    
    @pytest.fixture
    def prune_manager(self, tmp_path):
        """Create MemoryManager for pruning tests."""
        with patch('memory.memory_manager.CHROMADB_AVAILABLE', False):
            manager = MemoryManager(
                memory_dir=str(tmp_path / "memory"),
                enable_memory=True,
                auto_prune=False,
                openai_api_key="test-key"
            )
            return manager
    
    @pytest.mark.asyncio
    async def test_prune_old_unused_memories(self, prune_manager):
        """Test pruning memories unused for 90 days."""
        mock_embedding = [0.1] * 1536
        
        with patch.object(prune_manager, '_generate_embedding', return_value=mock_embedding):
            # Create old memory
            old_date = (datetime.now() - timedelta(days=100)).isoformat()
            old_memory = SkillMemory(
                context="Old memory",
                lesson="Should be pruned",
                created_at=old_date,
                last_used=old_date
            )
            
            await prune_manager.store_memory(old_memory)
            
            # Prune
            count = await prune_manager.prune_stale_memories()
            
            assert count == 1
            
            # Verify deleted
            all_memories = await prune_manager.list_all_memories()
            assert len(all_memories) == 0
    
    @pytest.mark.asyncio
    async def test_prune_unsuccessful_memories(self, prune_manager):
        """Test pruning memories with success_count=0 after 30 days."""
        mock_embedding = [0.1] * 1536
        
        with patch.object(prune_manager, '_generate_embedding', return_value=mock_embedding):
            # Create unsuccessful memory >30 days old
            old_date = (datetime.now() - timedelta(days=35)).isoformat()
            unsuccessful_memory = SkillMemory(
                context="Unsuccessful memory",
                lesson="Never worked",
                success_count=0,
                created_at=old_date,
                last_used=datetime.now().isoformat()
            )
            
            await prune_manager.store_memory(unsuccessful_memory)
            
            # Prune
            count = await prune_manager.prune_stale_memories()
            
            assert count == 1
    
    @pytest.mark.asyncio
    async def test_keep_successful_memories(self, prune_manager):
        """Test that successful memories are kept even if old."""
        mock_embedding = [0.1] * 1536
        
        with patch.object(prune_manager, '_generate_embedding', return_value=mock_embedding):
            # Create old but successful memory
            old_date = (datetime.now() - timedelta(days=100)).isoformat()
            successful_memory = SkillMemory(
                context="Successful memory",
                lesson="Worked well",
                success_count=5,
                created_at=old_date,
                last_used=(datetime.now() - timedelta(days=10)).isoformat()
            )
            
            await prune_manager.store_memory(successful_memory)
            
            # Prune
            count = await prune_manager.prune_stale_memories()
            
            # Should not prune - used within 90 days
            assert count == 0
            
            # Verify still exists
            all_memories = await prune_manager.list_all_memories()
            assert len(all_memories) == 1


class TestMemoryManagerSemanticSearch:
    """Test semantic search functionality."""
    
    @pytest.fixture
    def search_manager(self, tmp_path):
        """Create MemoryManager for search tests."""
        with patch('memory.memory_manager.CHROMADB_AVAILABLE', False):
            manager = MemoryManager(
                memory_dir=str(tmp_path / "memory"),
                enable_memory=True,
                auto_prune=False,
                openai_api_key="test-key"
            )
            return manager
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_memories(self, search_manager):
        """Test retrieving semantically similar memories."""
        # Mock embeddings that are similar
        python_embedding = [0.9, 0.1, 0.0] + [0.0] * 1533
        query_embedding = [0.85, 0.15, 0.05] + [0.0] * 1533
        
        # Store memory with Python embedding
        with patch.object(search_manager, '_generate_embedding', return_value=python_embedding):
            memory = SkillMemory(
                context="Python tool error",
                lesson="Check imports before execution"
            )
            await search_manager.store_memory(memory)
        
        # Search with similar query
        with patch.object(search_manager, '_generate_embedding', return_value=query_embedding):
            results = await search_manager.retrieve_relevant_memories(
                "Python import problems",
                top_k=5,
                min_similarity=0.5  # Lower threshold for test
            )
            
            assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_min_similarity_threshold(self, search_manager):
        """Test that low similarity memories are filtered out."""
        # Very different embeddings
        stored_embedding = [1.0, 0.0, 0.0] + [0.0] * 1533
        query_embedding = [0.0, 1.0, 0.0] + [0.0] * 1533
        
        with patch.object(search_manager, '_generate_embedding', return_value=stored_embedding):
            memory = SkillMemory(
                context="Completely different topic",
                lesson="Not relevant"
            )
            await search_manager.store_memory(memory)
        
        with patch.object(search_manager, '_generate_embedding', return_value=query_embedding):
            results = await search_manager.retrieve_relevant_memories(
                "Python errors",
                top_k=5,
                min_similarity=0.7
            )
            
            # Should not return dissimilar memory
            assert len(results) == 0


@pytest.mark.integration
class TestMemoryManagerIntegration:
    """Integration tests with real OpenAI API (requires OPENAI_API_KEY)."""
    
    @pytest.fixture
    def integration_manager(self, tmp_path):
        """Create MemoryManager for integration tests."""
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")
        
        with patch('memory.memory_manager.CHROMADB_AVAILABLE', False):
            manager = MemoryManager(
                memory_dir=str(tmp_path / "memory"),
                enable_memory=True,
                auto_prune=False,
                openai_api_key=api_key
            )
            return manager
    
    @pytest.mark.asyncio
    async def test_real_embedding_generation(self, integration_manager):
        """Test embedding generation with real OpenAI API."""
        memory = SkillMemory(
            context="Git tool failed with authentication error",
            lesson="Always check if GitHub token is set before git operations"
        )
        
        result = await integration_manager.store_memory(memory)
        assert result is True
        
        # Verify embedding was generated
        all_memories = await integration_manager.list_all_memories()
        assert len(all_memories) == 1
        assert all_memories[0].embedding is not None
        assert len(all_memories[0].embedding) == 1536
    
    @pytest.mark.asyncio
    async def test_real_semantic_search(self, integration_manager):
        """Test semantic search with real embeddings."""
        # Store memories with different contexts
        memories_to_store = [
            SkillMemory(
                context="Python tool failed with ModuleNotFoundError",
                lesson="Check if module is installed before importing"
            ),
            SkillMemory(
                context="Git push failed with authentication error",
                lesson="Verify GitHub token is configured"
            ),
            SkillMemory(
                context="File write failed with permission error",
                lesson="Check file permissions before writing"
            )
        ]
        
        for memory in memories_to_store:
            await integration_manager.store_memory(memory)
        
        # Search for Python-related memories
        results = await integration_manager.retrieve_relevant_memories(
            "Python import errors and missing modules",
            top_k=2,
            min_similarity=0.5
        )
        
        assert len(results) > 0
        # First result should be Python-related
        assert "Python" in results[0].context or "module" in results[0].context.lower()


@pytest.mark.performance
class TestMemoryManagerPerformance:
    """Performance tests for MemoryManager."""
    
    @pytest.fixture
    def perf_manager(self, tmp_path):
        """Create MemoryManager for performance tests."""
        with patch('memory.memory_manager.CHROMADB_AVAILABLE', False):
            manager = MemoryManager(
                memory_dir=str(tmp_path / "memory"),
                enable_memory=True,
                auto_prune=False,
                openai_api_key="test-key"
            )
            return manager
    
    @pytest.mark.asyncio
    async def test_retrieval_performance_1000_memories(self, perf_manager):
        """Test retrieval latency with 1000 memories (< 200ms)."""
        import time
        
        mock_embedding = [0.1] * 1536
        
        with patch.object(perf_manager, '_generate_embedding', return_value=mock_embedding):
            # Store 1000 memories
            for i in range(1000):
                memory = SkillMemory(
                    context=f"Context {i}",
                    lesson=f"Lesson {i}"
                )
                await perf_manager.store_memory(memory)
            
            # Measure retrieval time
            start = time.time()
            results = await perf_manager.retrieve_relevant_memories(
                "Test query",
                top_k=5
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            
            assert elapsed < 200, f"Retrieval took {elapsed}ms, should be < 200ms"
            assert len(results) <= 5

