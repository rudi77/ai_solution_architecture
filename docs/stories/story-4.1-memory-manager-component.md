# Story 4.1: Design and Implement MemoryManager Component - Brownfield Addition

## User Story

As an **agent architect**,
I want **a persistent memory storage system for learned skills and lessons**,
So that **the agent can recall past experiences across sessions and avoid repeating mistakes**.

## Story Context

**Existing System Integration:**

- Integrates with: Agent initialization, persistence layer (alongside StateManager)
- Technology: Python 3.11, asyncio, dataclasses, ChromaDB or JSON + embeddings
- Follows pattern: StateManager's persistence approach (async file I/O, directory structure)
- Touch points: Agent.__init__(), work_dir structure, async persistence

## Acceptance Criteria

### Functional Requirements

1. **Define `SkillMemory` dataclass**
   - Fields: `id` (UUID), `context` (str), `lesson` (str), `tool_name` (Optional[str]), `success_count` (int), `created_at` (datetime), `last_used` (datetime)
   - Serializable to JSON for persistence
   - Include `embedding` field (List[float]) for semantic search

2. **Create `MemoryManager` class with CRUD operations**
   - `__init__(memory_dir: str, enable_memory: bool = True)`
   - `async store_memory(memory: SkillMemory) -> bool`
   - `async retrieve_relevant_memories(query: str, top_k: int = 5) -> List[SkillMemory]`
   - `async list_all_memories() -> List[SkillMemory]`
   - `async delete_memory(memory_id: str) -> bool`
   - `async update_success_count(memory_id: str, increment: int = 1) -> bool`

3. **Implement lightweight vector store**
   - Option A: ChromaDB for semantic search (persistent, lightweight)
   - Option B: JSON file + simple cosine similarity (no external dependencies)
   - Store memories in `{work_dir}/memory/skills.db` (ChromaDB) or `skills.json`
   - Embeddings generated via OpenAI embeddings API (text-embedding-3-small)

4. **Implement semantic search method**
   - `retrieve_relevant_memories()` accepts natural language query
   - Generate query embedding, compute similarity with stored memories
   - Return top_k most relevant memories sorted by similarity score
   - Filter by minimum similarity threshold (0.7)

5. **Implement memory lifecycle management**
   - TTL: Memories unused for 90 days marked for pruning
   - Usage-based pruning: Memories with `success_count=0` after 30 days removed
   - Prune operation: `async prune_stale_memories() -> int` (returns count removed)
   - Automatic pruning on MemoryManager initialization (optional)

6. **Add graceful degradation for disabled memory**
   - If `enable_memory=False`, all methods no-op gracefully
   - No exceptions thrown, just log warning and return empty results
   - Agent works normally without memory system

### Integration Requirements

7. MemoryManager follows StateManager's async persistence pattern
8. Memory storage isolated in `{work_dir}/memory/` directory
9. No dependencies on StateManager or Agent internals (standalone component)
10. Embeddings API calls cached to avoid redundant requests

### Quality Requirements

11. Unit tests for SkillMemory dataclass and serialization
12. Unit tests for CRUD operations (store, retrieve, delete, update)
13. Unit tests for semantic search with various query types
14. Unit tests for memory pruning logic
15. Integration test with real embeddings API (OpenAI)
16. Performance test: retrieval latency < 200ms for 1000 memories

## Technical Notes

### Integration Approach

Create a new `MemoryManager` class similar to `StateManager` for persistence. Use ChromaDB (lightweight, embeddable) or a simple JSON + numpy approach for vector storage.

**Code Location:** `capstone/agent_v2/memory/memory_manager.py` (new module)

**Example Implementation:**

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import uuid
import json
import structlog

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

@dataclass
class SkillMemory:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: str = ""  # Situation when lesson learned
    lesson: str = ""  # The actual learning
    tool_name: Optional[str] = None
    success_count: int = 0  # Times this memory helped
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "context": self.context,
            "lesson": self.lesson,
            "tool_name": self.tool_name,
            "success_count": self.success_count,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "embedding": self.embedding
        }

class MemoryManager:
    """Persistent memory storage for agent learned skills"""
    
    def __init__(
        self, 
        memory_dir: str = "./memory",
        enable_memory: bool = True,
        auto_prune: bool = True
    ):
        self.memory_dir = Path(memory_dir)
        self.enable_memory = enable_memory
        self.logger = structlog.get_logger()
        
        if not enable_memory:
            self.logger.warning("Memory system disabled")
            return
        
        self.memory_dir.mkdir(exist_ok=True)
        
        # Initialize vector store
        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(path=str(self.memory_dir))
            self.collection = self.client.get_or_create_collection("skills")
        else:
            self.logger.warning("ChromaDB not available, using JSON fallback")
            self.skills_file = self.memory_dir / "skills.json"
            self._load_json_store()
        
        if auto_prune:
            asyncio.create_task(self.prune_stale_memories())
    
    async def store_memory(self, memory: SkillMemory) -> bool:
        """Store a skill memory with embedding"""
        if not self.enable_memory:
            return False
        
        # Generate embedding if not provided
        if memory.embedding is None:
            memory.embedding = await self._generate_embedding(
                f"{memory.context} {memory.lesson}"
            )
        
        # Store in vector DB
        if CHROMADB_AVAILABLE:
            self.collection.add(
                ids=[memory.id],
                embeddings=[memory.embedding],
                metadatas=[memory.to_dict()]
            )
        else:
            self.json_store[memory.id] = memory.to_dict()
            await self._save_json_store()
        
        self.logger.info("Stored memory", memory_id=memory.id)
        return True
    
    async def retrieve_relevant_memories(
        self, 
        query: str, 
        top_k: int = 5
    ) -> List[SkillMemory]:
        """Semantic search for relevant memories"""
        if not self.enable_memory:
            return []
        
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)
        
        if CHROMADB_AVAILABLE:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            memories = [
                SkillMemory(**metadata) 
                for metadata in results["metadatas"][0]
            ]
        else:
            # Simple cosine similarity fallback
            memories = self._cosine_search(query_embedding, top_k)
        
        # Update last_used timestamp
        for memory in memories:
            memory.last_used = datetime.now()
            await self.update_success_count(memory.id, 0)  # Touch only
        
        return memories
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
```

### Existing Pattern Reference

Follow StateManager's patterns:
- Async file I/O with aiofiles
- Directory structure under work_dir
- Structured logging with operation context
- Graceful degradation (enable/disable flag)

### Key Constraints

- Memory retrieval must be < 200ms for performance
- Embeddings API calls must be cached/batched
- Memory storage isolated from StateManager (no coupling)
- Must work without ChromaDB (JSON fallback)

## Definition of Done

- [x] `SkillMemory` dataclass defined with all fields
- [x] `MemoryManager` class with CRUD operations implemented
- [x] Lightweight vector store (ChromaDB or JSON) functional
- [x] Semantic search returns relevant memories (top_k)
- [x] Memory lifecycle management (TTL, pruning) implemented
- [x] Graceful degradation for `enable_memory=False`
- [x] Unit tests pass for dataclass, CRUD, search, pruning
- [x] Integration test with real embeddings API passes
- [x] Performance benchmark: < 200ms retrieval for 1000 memories

## Risk and Compatibility Check

### Minimal Risk Assessment

**Primary Risk:** Embeddings API costs escalate with frequent queries; ChromaDB dependency issues

**Mitigation:**
- Embedding caching reduces API calls
- JSON fallback if ChromaDB unavailable
- `enable_memory=False` allows complete disable
- Simple cosine similarity fallback for JSON mode

**Rollback:**
- Set `enable_memory=False` in Agent initialization
- Delete `memory/` directory to clear storage
- No impact on Agent core functionality (standalone component)

### Compatibility Verification

- [x] No dependencies on Agent or StateManager internals
- [x] Memory directory isolated from state_dir
- [x] Agent works without memory system (optional component)
- [x] No breaking changes to existing Agent API

## Validation Checklist

### Scope Validation

- [x] Story can be completed in one development session (~5-6 hours)
- [x] Integration is standalone component (no complex coupling)
- [x] Follows StateManager persistence pattern
- [x] ChromaDB simple to integrate (or JSON fallback)

### Clarity Check

- [x] Story requirements are unambiguous
- [x] Integration points clearly specified (standalone component)
- [x] Success criteria testable via unit + integration tests
- [x] Rollback approach is simple (disable flag)

