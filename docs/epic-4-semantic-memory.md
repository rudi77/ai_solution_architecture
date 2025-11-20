# Epic 4: Semantic Long-term Memory (Learned Skills) - Brownfield Enhancement

## Epic Goal

Implement a persistent learning system that captures "lessons learned" from failures and successes across sessions, allowing the agent to recall and apply past experiences to avoid repeating mistakes and improve decision-making over time.

## Epic Description

### Existing System Context

**Current relevant functionality:**
- ReAct agent with session-based execution (StateManager for persistence)
- TodoList planning via LLMService with MessageHistory context
- Tool execution with failure tracking and retry logic
- Each new session starts with clean slate (no cross-session memory)
- MessageHistory compression for long conversations (within session only)

**Technology stack:**
- Python 3.11 with asyncio
- LLMService for decision-making and planning
- StateManager for session state persistence (JSON/pickle)
- Structured logging with execution context

**Integration points:**
- Agent initialization (load memory context for system prompt)
- Tool execution failure/success path (extract lessons)
- TodoListManager plan generation (inject relevant memories)
- MessageHistory system prompt (augment with recalled skills)

### Enhancement Details

**What's being added/changed:**
- Create `MemoryManager` component for skill persistence and retrieval
- Implement lesson extraction from execution outcomes (failure → retry → success patterns)
- Add semantic search for relevant memories during planning/execution
- Use lightweight vector store (ChromaDB or JSON + embeddings) for skill storage
- Structure memories as: context, lesson, success_count, last_used

**How it integrates:**
- MemoryManager initialized alongside StateManager in Agent
- Post-execution hook extracts lessons from completed TodoItems
- Pre-planning hook retrieves relevant memories for LLM context
- Memories injected into system prompt or MessageHistory for decision-making
- Persistent storage in `{work_dir}/memory/skills.db`

**Success criteria:**
- Agent learns from failures across sessions (e.g., "pandas not available, use csv module")
- Relevant memories retrieved based on mission context (semantic similarity)
- Memory retrieval latency < 200ms for planning phase
- Agent success rate improves by 20% on repeated similar tasks
- Maximum 5 most relevant memories injected per planning cycle

## Stories

1. **Story 4.1: Design and Implement MemoryManager Component**
   - Create `MemoryManager` class with CRUD operations for memories
   - Define `SkillMemory` dataclass: id, context, lesson, tool_name, success_count, created_at, last_used
   - Implement lightweight vector store (ChromaDB or JSON + simple embedding)
   - Add semantic search method `retrieve_relevant_memories(query, top_k=5)`
   - Implement memory persistence to `{work_dir}/memory/skills.db`
   - Add memory lifecycle management (TTL, usage-based pruning)

2. **Story 4.2: Implement Lesson Extraction from Execution Outcomes**
   - Add post-execution hook in `Agent._execute_action()` for completed/failed steps
   - Implement lesson extraction logic for failure → success patterns
   - Create extraction heuristics:
     - Tool substitution (failed tool A → succeeded with tool B)
     - Parameter correction (failed with params X → succeeded with params Y)
     - Environmental constraints (library not available, use alternative)
   - Use LLM to generate structured lesson from execution trace
   - Store extracted lessons in MemoryManager

3. **Story 4.3: Integrate Memory Retrieval into Planning and Execution**
   - Add memory retrieval in `TodoListManager` before plan generation
   - Inject top 5 relevant memories into LLM planning prompt
   - Update Agent system prompt template to include memory context slot
   - Add memory recall logging for observability
   - Implement feedback loop: increment `success_count` when memory helps
   - Create integration tests with repeated task scenarios
   - Add CLI command `agent memory list` to inspect learned skills

## Compatibility Requirements

- [x] MemoryManager is optional component (graceful degradation if disabled)
- [x] No changes to core Agent/Tool/TodoList interfaces
- [x] Memory storage isolated in separate directory (`memory/`)
- [x] Existing StateManager unchanged (memory is separate persistence layer)
- [x] Agent works without memory system if MemoryManager not initialized

## Risk Mitigation

**Primary Risk:** Incorrect memories persist and poison future decisions; retrieval latency slows planning

**Mitigation:**
- Memories include success_count metric (low-confidence memories filtered)
- TTL and usage-based pruning removes stale/low-value memories
- Semantic search limited to top_k=5 to control latency and context size
- Memory injection is advisory only (LLM can ignore if irrelevant)
- CLI tool allows manual memory inspection and deletion

**Rollback Plan:**
- Set `enable_memory=False` in Agent initialization
- MemoryManager gracefully no-ops if disabled
- Delete `memory/` directory to clear all learned skills
- No code changes required in Agent/Tool classes for rollback

## Definition of Done

- [x] All stories completed with acceptance criteria met
- [x] MemoryManager component stores and retrieves skills persistently
- [x] Lessons extracted from failure → success execution patterns
- [x] Semantic memory retrieval integrated into planning phase
- [x] Top 5 relevant memories injected into LLM context per cycle
- [x] Memory retrieval latency < 200ms (measured)
- [x] Agent demonstrates improved performance on repeated similar tasks
- [x] CLI command `agent memory list` displays learned skills
- [x] Integration tests validate memory learning and recall
- [x] Existing functionality verified through regression testing (memory disabled)
- [x] Documentation updated with memory system architecture and CLI usage

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing ReAct agent running Python 3.11 with LLM-based planning
- Integration points:
  - New `MemoryManager` component alongside StateManager
  - Agent initialization (load memory context)
  - Post-execution hook in `Agent._execute_action()` for lesson extraction
  - Pre-planning hook in `TodoListManager` for memory retrieval
  - MessageHistory/system prompt for memory injection
- Existing patterns to follow:
  - Component-based architecture (MemoryManager similar to StateManager)
  - Async operations with structured logging
  - LLM-based extraction with structured prompts
  - Persistence layer isolated in work_dir subdirectory
- Critical compatibility requirements:
  - MemoryManager must be optional (enable_memory flag)
  - Zero impact on performance when memory disabled
  - No changes to core Agent/Tool/TodoList APIs
  - Memory storage isolated from StateManager persistence
  - Graceful degradation if vector store unavailable
- Each story must include verification that existing execution (memory disabled) remains intact
- Must test memory scenarios:
  - Learn from Python library unavailability
  - Learn from tool substitution (PowerShell → Python for file ops)
  - Learn from parameter corrections (incorrect API format)
  - Memory recall in new session for similar task
- Consider lightweight implementation (avoid heavy vector DB dependencies if possible)

The epic should maintain system integrity while delivering cross-session learning capabilities for improved agent resilience."

