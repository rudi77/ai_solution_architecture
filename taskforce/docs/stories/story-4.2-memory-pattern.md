# Story 4.2: Context-Aware Memory Pattern (Redundancy Check)

**Epic**: Agent Execution Efficiency Optimization  
**Story ID**: 4.2  
**Status**: Ready for Review  
**Priority**: High  
**Estimated Points**: 5  
**Dependencies**: Story 4.1 (Prompt Optimization)

---

## User Story

As a **platform operator**,  
I want **the agent to check its conversation history and previous results before making tool calls**,  
so that **redundant API calls are eliminated and response time is improved**.

---

## Acceptance Criteria

1. ✅ Extend `_build_thought_context()` to include full conversation history (not just last 5 results)
2. ✅ System prompt explicitly instructs agent to check `PREVIOUS_RESULTS` and `CONVERSATION_HISTORY` before any tool call
3. ✅ Implement `ToolResultCache` class for session-scoped caching of tool results
4. ✅ Cache key based on tool name + normalized input parameters
5. ✅ Cache TTL configurable per tool type (default: session lifetime)
6. ✅ Agent skips redundant tool calls when identical request found in cache or history
7. ✅ Trace logs show "CACHE_HIT" when redundant call is avoided
8. ✅ Unit tests verify cache behavior and history utilization

---

## Integration Verification

- **IV1: Existing Functionality** - All existing tests pass; caching is transparent
- **IV2: Integration Point** - Tool execution still works; cache is additive optimization
- **IV3: Performance** - Redundant tool calls reduced to zero in conversation flows

---

## Technical Notes

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent.execute()                       │
├─────────────────────────────────────────────────────────────┤
│  1. Build Context                                            │
│     ├── PREVIOUS_RESULTS (from TodoList completed steps)     │
│     ├── CONVERSATION_HISTORY (from state)                    │
│     └── TOOL_RESULT_CACHE (new: session-scoped cache)        │
│                                                              │
│  2. Generate Thought                                         │
│     └── LLM checks context BEFORE deciding on tool call      │
│                                                              │
│  3. Execute Action (if tool_call)                            │
│     ├── Check ToolResultCache for identical request          │
│     │   ├── CACHE_HIT: Return cached result                  │
│     │   └── CACHE_MISS: Execute tool, store in cache         │
│     └── Return observation                                   │
└─────────────────────────────────────────────────────────────┘
```

### ToolResultCache Implementation

```python
# infrastructure/cache/tool_cache.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import hashlib
import json


@dataclass
class CacheEntry:
    """Single cached tool result."""
    tool_name: str
    input_hash: str
    result: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 3600  # Default 1 hour


class ToolResultCache:
    """
    Session-scoped cache for tool execution results.
    
    Prevents redundant tool calls by storing results keyed by
    tool name + normalized input parameters.
    """
    
    def __init__(self, default_ttl: int = 3600):
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0}
    
    def _compute_key(self, tool_name: str, tool_input: dict) -> str:
        """Generate deterministic cache key from tool name and input."""
        # Normalize input by sorting keys
        normalized = json.dumps(tool_input, sort_keys=True, default=str)
        input_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{tool_name}:{input_hash}"
    
    def get(self, tool_name: str, tool_input: dict) -> dict[str, Any] | None:
        """
        Retrieve cached result if available and not expired.
        
        Returns:
            Cached result dict or None if cache miss
        """
        key = self._compute_key(tool_name, tool_input)
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats["misses"] += 1
            return None
        
        # Check TTL
        age = (datetime.utcnow() - entry.created_at).total_seconds()
        if age > entry.ttl_seconds:
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        self._stats["hits"] += 1
        return entry.result
    
    def put(
        self, 
        tool_name: str, 
        tool_input: dict, 
        result: dict[str, Any],
        ttl: int | None = None
    ) -> None:
        """Store tool result in cache."""
        key = self._compute_key(tool_name, tool_input)
        self._cache[key] = CacheEntry(
            tool_name=tool_name,
            input_hash=key.split(":")[1],
            result=result,
            ttl_seconds=ttl or self._default_ttl
        )
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0}
    
    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        return self._stats.copy()
```

### Agent Integration

```python
# core/domain/agent.py - Changes to _execute_tool()

async def _execute_tool(self, action: Action, step: TodoItem) -> Observation:
    """Execute tool with caching support."""
    tool = self.tools.get(action.tool)
    if not tool:
        return Observation(success=False, error=f"Tool not found: {action.tool}")
    
    # NEW: Check cache first
    if self._tool_cache:
        cached = self._tool_cache.get(action.tool, action.tool_input or {})
        if cached is not None:
            self.logger.info(
                "tool_cache_hit",
                tool=action.tool,
                step=step.position
            )
            return Observation(success=cached.get("success", True), data=cached)
    
    try:
        self.logger.info("tool_execution_start", tool=action.tool, step=step.position)
        result = await tool.execute(**(action.tool_input or {}))
        self.logger.info("tool_execution_end", tool=action.tool, step=step.position)
        
        # NEW: Cache successful results
        if self._tool_cache and result.get("success", False):
            # Only cache read-only tools (not mutations)
            if self._is_cacheable_tool(action.tool):
                self._tool_cache.put(action.tool, action.tool_input or {}, result)
        
        return Observation(success=result.get("success", False), data=result, error=result.get("error"))
    except Exception as e:
        self.logger.error("tool_execution_exception", tool=action.tool, error=str(e))
        return Observation(success=False, error=str(e))

def _is_cacheable_tool(self, tool_name: str) -> bool:
    """Determine if tool results should be cached (read-only tools only)."""
    # Whitelist of cacheable (read-only) tools
    cacheable = {
        "wiki_get_page", "wiki_get_page_tree", "wiki_search",
        "file_read", "semantic_search", "web_search",
        "get_document", "list_documents"
    }
    return tool_name in cacheable
```

### Enhanced Context Building

```python
# core/domain/agent.py - Changes to _build_thought_context()

def _build_thought_context(
    self, step: TodoItem, todolist: TodoList, state: dict[str, Any]
) -> dict[str, Any]:
    """Build enriched context for thought generation."""
    
    # Collect ALL results from completed steps (not just last 5)
    previous_results = [
        {
            "step": s.position,
            "description": s.description,
            "tool": s.chosen_tool,
            "result": s.execution_result,
            "status": s.status.value,
        }
        for s in todolist.items
        if s.execution_result and s.position < step.position
    ]
    
    # NEW: Include full conversation history
    conversation_history = state.get("conversation_history", [])
    
    # NEW: Include cache stats for transparency
    cache_info = None
    if self._tool_cache:
        cache_info = {
            "enabled": True,
            "stats": self._tool_cache.stats,
            "hint": "Check PREVIOUS_RESULTS before calling tools - data may already be available"
        }
    
    return {
        "current_step": step,
        "previous_results": previous_results,  # CHANGED: All results, not truncated
        "conversation_history": conversation_history,  # NEW
        "cache_info": cache_info,  # NEW
        "user_answers": state.get("answers", {}),
    }
```

### System Prompt Enhancement

Add to the existing optimized prompt (from Story 4.1):

```python
# Add to EXECUTION_AGENT_PROMPT

"""
## MEMORY UTILIZATION PROTOCOL

Before ANY tool call, you MUST perform this checklist:

### Step 1: Check PREVIOUS_RESULTS
Scan the `PREVIOUS_RESULTS` array for:
- Same tool with same or similar parameters
- Data that answers your current question
- Related information that makes the tool call unnecessary

### Step 2: Check CONVERSATION_HISTORY
Review recent conversation turns for:
- User-provided information
- Previous agent responses containing relevant data
- Context that eliminates need for tool call

### Step 3: Decision
- If data found → Use it directly in `finish_step.summary`
- If data not found → Proceed with minimal tool call

### Example - Correct Behavior:

PREVIOUS_RESULTS contains:
  {"tool": "wiki_get_page_tree", "result": {"pages": [{"title": "Copilot", "id": 42}]}}

User asks: "What subpages are there?"

CORRECT: Return finish_step with summary: "The available subpages are: Copilot (ID: 42)"
WRONG: Call wiki_get_page_tree again

"""
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/infrastructure/test_tool_cache.py

import pytest
from datetime import datetime, timedelta
from taskforce.infrastructure.cache.tool_cache import ToolResultCache


def test_cache_hit():
    """Test cache returns stored result."""
    cache = ToolResultCache()
    
    cache.put("wiki_get_page", {"path": "/Home"}, {"success": True, "content": "Hello"})
    result = cache.get("wiki_get_page", {"path": "/Home"})
    
    assert result is not None
    assert result["content"] == "Hello"
    assert cache.stats["hits"] == 1


def test_cache_miss():
    """Test cache returns None for unknown key."""
    cache = ToolResultCache()
    
    result = cache.get("unknown_tool", {"param": "value"})
    
    assert result is None
    assert cache.stats["misses"] == 1


def test_cache_key_normalization():
    """Test cache key is deterministic regardless of dict order."""
    cache = ToolResultCache()
    
    # Store with one key order
    cache.put("tool", {"b": 2, "a": 1}, {"result": "data"})
    
    # Retrieve with different key order
    result = cache.get("tool", {"a": 1, "b": 2})
    
    assert result is not None
    assert result["result"] == "data"


def test_cache_ttl_expiration():
    """Test cache entries expire after TTL."""
    cache = ToolResultCache(default_ttl=1)  # 1 second TTL
    
    cache.put("tool", {"key": "value"}, {"result": "data"})
    
    # Manually expire by modifying created_at
    key = cache._compute_key("tool", {"key": "value"})
    cache._cache[key].created_at = datetime.utcnow() - timedelta(seconds=2)
    
    result = cache.get("tool", {"key": "value"})
    
    assert result is None  # Expired
    assert cache.stats["misses"] == 1
```

### Integration Tests

```python
# tests/integration/test_memory_pattern.py

@pytest.mark.integration
async def test_agent_uses_cached_result():
    """
    Given: Agent has previously fetched wiki page tree
    When: User asks about the same data
    Then: Agent uses cached result instead of calling tool again
    """
    cache = ToolResultCache()
    agent = await AgentFactory.create_standard_agent(config, tool_cache=cache)
    
    # First execution - should call tool
    result1 = await agent.execute(
        mission="List all wiki pages",
        session_id="test-cache"
    )
    
    assert cache.stats["misses"] >= 1
    initial_misses = cache.stats["misses"]
    
    # Second execution with related question - should use cache
    result2 = await agent.execute(
        mission="How many wiki pages are there?",
        session_id="test-cache"
    )
    
    # Cache hits should increase, misses should not
    assert cache.stats["hits"] >= 1
    assert cache.stats["misses"] == initial_misses


@pytest.mark.integration
async def test_agent_checks_previous_results():
    """
    Given: Previous step already fetched required data
    When: Current step needs the same data
    Then: Agent references PREVIOUS_RESULTS instead of re-fetching
    """
    # This test verifies the LLM behavior via trace analysis
    agent = await AgentFactory.create_standard_agent(config)
    
    result = await agent.execute(
        mission="First, list all wiki pages. Then tell me how many there are.",
        session_id="test-prev-results"
    )
    
    # Count tool calls to wiki_get_page_tree
    wiki_calls = sum(
        1 for entry in result.execution_history
        if entry["type"] == "thought" 
        and entry["data"]["action"].get("tool") == "wiki_get_page_tree"
    )
    
    # Should only call once, not twice
    assert wiki_calls == 1, f"Expected 1 wiki call, got {wiki_calls}"
```

---

## Definition of Done

- [x] `ToolResultCache` class implemented in `infrastructure/cache/tool_cache.py`
- [x] Agent constructor accepts optional `tool_cache` parameter
- [x] `_execute_tool()` checks cache before execution
- [x] `_build_thought_context()` includes full conversation history
- [x] System prompt updated with MEMORY UTILIZATION PROTOCOL
- [x] Cacheable tool whitelist defined
- [x] Unit tests for cache behavior (hit, miss, TTL, key normalization)
- [x] Integration test verifies redundant calls are eliminated
- [x] Trace logs show "tool_cache_hit" events
- [x] Documentation updated
- [ ] Code review completed

---

## Files to Create/Modify

**Create:**
- `taskforce/src/taskforce/infrastructure/cache/__init__.py`
- `taskforce/src/taskforce/infrastructure/cache/tool_cache.py` - ToolResultCache class
- `taskforce/tests/unit/infrastructure/test_tool_cache.py` - Cache unit tests
- `taskforce/tests/integration/test_memory_pattern.py` - Redundancy elimination tests

**Modify:**
- `taskforce/src/taskforce/core/domain/agent.py` - Add `_tool_cache` attribute, modify `_execute_tool()` (line ~708)
- `taskforce/src/taskforce/core/prompts/autonomous_prompts.py` - Already has "MEMORY FIRST" rule from Story 4.1
- `taskforce/src/taskforce/application/factory.py` - Inject `ToolResultCache` into Agent constructor

---

## Rollback Plan

1. Set `enable_tool_cache: false` in config
2. Cache is additive - removing it doesn't break functionality
3. Prompt changes can be reverted independently

---

## Dev Agent Record

### Agent Model Used
Claude Opus 4.5 (James - Full Stack Developer)

### File List

**Created:**
- `taskforce/src/taskforce/infrastructure/cache/__init__.py` - Cache module init
- `taskforce/src/taskforce/infrastructure/cache/tool_cache.py` - ToolResultCache class with TTL support
- `taskforce/tests/unit/infrastructure/cache/__init__.py` - Cache tests init
- `taskforce/tests/unit/infrastructure/cache/test_tool_cache.py` - 18 unit tests for cache
- `taskforce/tests/integration/test_memory_pattern.py` - 9 integration tests for memory pattern

**Modified:**
- `taskforce/src/taskforce/core/domain/agent.py` - Added CACHEABLE_TOOLS whitelist, tool_cache param, cache logic in _execute_tool(), enhanced _build_thought_context()
- `taskforce/src/taskforce/core/prompts/autonomous_prompts.py` - Enhanced MEMORY FIRST with detailed checklist and example
- `taskforce/src/taskforce/application/factory.py` - Inject ToolResultCache in create_agent() and create_rag_agent()

### Change Log
- Implemented ToolResultCache with deterministic key generation, TTL support, and statistics tracking
- Added cache support to Agent class with configurable whitelist of cacheable (read-only) tools
- Enhanced context building to include full conversation history (not truncated) and cache info
- Updated system prompt with detailed MEMORY UTILIZATION PROTOCOL including 3-step checklist
- Factory now auto-creates cache with configurable TTL (config: `cache.tool_cache_ttl`, `cache.enable_tool_cache`)
- All 18 cache unit tests pass (hit/miss/TTL/key normalization/clear/invalidate)
- All 9 integration tests pass (cache integration, context building, whitelist)
- All 17 existing agent unit tests pass (no regression)

### Completion Notes
- Cache is session-scoped (created per agent instance by factory)
- Only read-only tools are cacheable (wiki_get_page, file_read, semantic_search, etc.)
- Write/mutation tools (file_write, git_commit, powershell) are never cached
- TTL defaults to 3600s (1 hour); set to 0 for session-lifetime (no expiry)
- Cache can be disabled via config: `cache.enable_tool_cache: false`
- Trace logs emit "tool_cache_hit" and "tool_result_cached" events for observability
