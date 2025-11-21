"""Persistent memory storage for agent learned skills and lessons."""

import asyncio
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
import structlog
import aiofiles
import math

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class SkillMemory:
    """Represents a learned skill or lesson from agent execution."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: str = ""  # Situation when lesson learned
    lesson: str = ""  # The actual learning
    tool_name: Optional[str] = None
    success_count: int = 0  # Times this memory helped
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillMemory":
        """Deserialize from dictionary."""
        return cls(**data)


class MemoryManager:
    """Persistent memory storage for agent learned skills."""
    
    def __init__(
        self, 
        memory_dir: str = "./memory",
        enable_memory: bool = True,
        auto_prune: bool = True,
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize MemoryManager.
        
        Args:
            memory_dir: Directory for memory storage
            enable_memory: Enable/disable memory system
            auto_prune: Automatically prune stale memories on init
            openai_api_key: OpenAI API key for embeddings
        """
        self.memory_dir = Path(memory_dir)
        self.enable_memory = enable_memory
        self.logger = structlog.get_logger(__name__)
        self.openai_api_key = openai_api_key
        self._embedding_cache: Dict[str, List[float]] = {}
        
        if not enable_memory:
            self.logger.warning("Memory system disabled")
            return
        
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize vector store
        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(
                    path=str(self.memory_dir / "chroma_db"),
                    settings=Settings(anonymized_telemetry=False)
                )
                self.collection = self.client.get_or_create_collection(
                    name="skills",
                    metadata={"hnsw:space": "cosine"}
                )
                self.use_chromadb = True
                self.logger.info("ChromaDB initialized", path=str(self.memory_dir / "chroma_db"))
            except Exception as e:
                self.logger.warning(f"ChromaDB initialization failed, using JSON fallback: {e}")
                self.use_chromadb = False
                self._init_json_store()
        else:
            self.logger.warning("ChromaDB not available, using JSON fallback")
            self.use_chromadb = False
            self._init_json_store()
        
        if auto_prune:
            # Schedule async pruning without blocking
            asyncio.create_task(self._auto_prune())
    
    def _init_json_store(self):
        """Initialize JSON-based storage."""
        self.skills_file = self.memory_dir / "skills.json"
        self.json_store: Dict[str, Dict[str, Any]] = {}
        if self.skills_file.exists():
            with open(self.skills_file, 'r', encoding='utf-8') as f:
                self.json_store = json.load(f)
    
    async def _auto_prune(self):
        """Auto-prune stale memories on initialization."""
        try:
            count = await self.prune_stale_memories()
            if count > 0:
                self.logger.info(f"Auto-pruned {count} stale memories")
        except Exception as e:
            self.logger.error(f"Auto-prune failed: {e}")
    
    async def store_memory(self, memory: SkillMemory) -> bool:
        """
        Store a skill memory with embedding.
        
        Args:
            memory: SkillMemory to store
            
        Returns:
            True if stored successfully
        """
        if not self.enable_memory:
            return False
        
        try:
            # Generate embedding if not provided
            if memory.embedding is None:
                memory.embedding = await self._generate_embedding(
                    f"{memory.context} {memory.lesson}"
                )
            
            # Store in vector DB
            if self.use_chromadb:
                # ChromaDB stores metadata separately
                metadata = {
                    "id": memory.id,
                    "context": memory.context,
                    "lesson": memory.lesson,
                    "tool_name": memory.tool_name or "",
                    "success_count": memory.success_count,
                    "created_at": memory.created_at,
                    "last_used": memory.last_used
                }
                
                self.collection.upsert(
                    ids=[memory.id],
                    embeddings=[memory.embedding],
                    metadatas=[metadata]
                )
            else:
                self.json_store[memory.id] = memory.to_dict()
                await self._save_json_store()
            
            self.logger.info("Stored memory", memory_id=memory.id, context=memory.context[:50])
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}", memory_id=memory.id)
            return False
    
    async def retrieve_relevant_memories(
        self, 
        query: str, 
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[SkillMemory]:
        """
        Semantic search for relevant memories.
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of relevant SkillMemory objects
        """
        if not self.enable_memory:
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            if self.use_chromadb:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, self.collection.count())
                )
                
                if not results["metadatas"] or not results["metadatas"][0]:
                    return []
                
                memories = []
                distances = results.get("distances", [[]])[0]
                
                for idx, metadata in enumerate(results["metadatas"][0]):
                    # ChromaDB returns distance, convert to similarity
                    similarity = 1.0 - (distances[idx] if idx < len(distances) else 1.0)
                    
                    if similarity >= min_similarity:
                        memory = SkillMemory(
                            id=metadata["id"],
                            context=metadata["context"],
                            lesson=metadata["lesson"],
                            tool_name=metadata.get("tool_name") or None,
                            success_count=metadata["success_count"],
                            created_at=metadata["created_at"],
                            last_used=metadata["last_used"]
                        )
                        memories.append(memory)
            else:
                # JSON fallback with cosine similarity
                memories = await self._cosine_search(query_embedding, top_k, min_similarity)
            
            # Update last_used timestamp
            for memory in memories:
                memory.last_used = datetime.now().isoformat()
                await self.update_success_count(memory.id, 0)  # Touch only
            
            self.logger.info(f"Retrieved {len(memories)} relevant memories", query=query[:50])
            return memories
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve memories: {e}")
            return []
    
    async def list_all_memories(self) -> List[SkillMemory]:
        """
        List all stored memories.
        
        Returns:
            List of all SkillMemory objects
        """
        if not self.enable_memory:
            return []
        
        try:
            if self.use_chromadb:
                results = self.collection.get()
                
                if not results["metadatas"]:
                    return []
                
                memories = []
                for metadata in results["metadatas"]:
                    memory = SkillMemory(
                        id=metadata["id"],
                        context=metadata["context"],
                        lesson=metadata["lesson"],
                        tool_name=metadata.get("tool_name") or None,
                        success_count=metadata["success_count"],
                        created_at=metadata["created_at"],
                        last_used=metadata["last_used"]
                    )
                    memories.append(memory)
                
                return memories
            else:
                return [SkillMemory.from_dict(data) for data in self.json_store.values()]
                
        except Exception as e:
            self.logger.error(f"Failed to list memories: {e}")
            return []
    
    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: ID of memory to delete
            
        Returns:
            True if deleted successfully
        """
        if not self.enable_memory:
            return False
        
        try:
            if self.use_chromadb:
                self.collection.delete(ids=[memory_id])
            else:
                if memory_id in self.json_store:
                    del self.json_store[memory_id]
                    await self._save_json_store()
                else:
                    return False
            
            self.logger.info("Deleted memory", memory_id=memory_id)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete memory: {e}", memory_id=memory_id)
            return False
    
    async def update_success_count(self, memory_id: str, increment: int = 1) -> bool:
        """
        Update success count for a memory.
        
        Args:
            memory_id: ID of memory to update
            increment: Amount to increment (0 to just touch last_used)
            
        Returns:
            True if updated successfully
        """
        if not self.enable_memory:
            return False
        
        try:
            if self.use_chromadb:
                # Get current memory
                results = self.collection.get(ids=[memory_id])
                if not results["metadatas"]:
                    return False
                
                metadata = results["metadatas"][0]
                metadata["success_count"] += increment
                metadata["last_used"] = datetime.now().isoformat()
                
                # Update
                self.collection.update(
                    ids=[memory_id],
                    metadatas=[metadata]
                )
            else:
                if memory_id in self.json_store:
                    self.json_store[memory_id]["success_count"] += increment
                    self.json_store[memory_id]["last_used"] = datetime.now().isoformat()
                    await self._save_json_store()
                else:
                    return False
            
            if increment > 0:
                self.logger.debug("Updated memory success count", memory_id=memory_id, increment=increment)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update success count: {e}", memory_id=memory_id)
            return False
    
    async def prune_stale_memories(self) -> int:
        """
        Remove stale memories based on TTL and usage.
        
        - Memories unused for 90 days are removed
        - Memories with success_count=0 after 30 days are removed
        
        Returns:
            Count of memories removed
        """
        if not self.enable_memory:
            return 0
        
        try:
            now = datetime.now()
            ttl_threshold = now - timedelta(days=90)
            unused_threshold = now - timedelta(days=30)
            
            memories_to_delete = []
            all_memories = await self.list_all_memories()
            
            for memory in all_memories:
                last_used = datetime.fromisoformat(memory.last_used)
                created = datetime.fromisoformat(memory.created_at)
                
                # Remove if unused for 90 days
                if last_used < ttl_threshold:
                    memories_to_delete.append(memory.id)
                # Remove if unused and created >30 days ago with no success
                elif memory.success_count == 0 and created < unused_threshold:
                    memories_to_delete.append(memory.id)
            
            # Delete marked memories
            for memory_id in memories_to_delete:
                await self.delete_memory(memory_id)
            
            if memories_to_delete:
                self.logger.info(f"Pruned {len(memories_to_delete)} stale memories")
            
            return len(memories_to_delete)
            
        except Exception as e:
            self.logger.error(f"Failed to prune memories: {e}")
            return 0
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API with caching.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # Check cache
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.openai_api_key)
            
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # Cache result
            self._embedding_cache[text] = embedding
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 1536  # text-embedding-3-small dimension
    
    async def _cosine_search(
        self, 
        query_embedding: List[float], 
        top_k: int,
        min_similarity: float
    ) -> List[SkillMemory]:
        """
        Simple cosine similarity search for JSON fallback.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of relevant memories
        """
        results = []
        
        for memory_data in self.json_store.values():
            if not memory_data.get("embedding"):
                continue
            
            memory_embedding = memory_data["embedding"]
            similarity = self._cosine_similarity(query_embedding, memory_embedding)
            
            if similarity >= min_similarity:
                memory = SkillMemory.from_dict(memory_data)
                results.append((similarity, memory))
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[0], reverse=True)
        return [memory for _, memory in results[:top_k]]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _save_json_store(self):
        """Save JSON store to disk."""
        async with aiofiles.open(self.skills_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(self.json_store, indent=2))

