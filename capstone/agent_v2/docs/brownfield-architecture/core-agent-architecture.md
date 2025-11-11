# Core Agent Architecture

### ReAct Execution Loop

The agent follows this flow (per CLAUDE.md):

```
1. Load State: Restore session from disk via StateManager
2. Set Mission: Define objective (if first run)
3. Create/Load Plan: Generate TodoList using TodoListManager
4. Execute Loop: For each pending TodoItem:
   a. Generate Thought (rationale + action decision)
   b. Execute Action (tool_call, ask_user, replan, or complete)
   c. Record Observation (success/failure + result data)
   d. Update state and persist to disk
5. Complete: All TodoItems resolved or mission goal achieved
```

**Key Files**:
- Main loop: `agent.py:Agent.run()` method (estimated around line 300-500 based on file size)
- State persistence: After each action via `StateManager.save_state()`
- Message management: `MessageHistory` maintains rolling window (last N message pairs)

### Message History Management

**Location**: `agent.py:73-165`

**Behavior**:
- Always includes system prompt as first message
- Rolling window of last N message pairs (user + assistant)
- Auto-compression when exceeding `SUMMARY_THRESHOLD` (40 messages)
- Compression uses LLM to summarize old context (model: gpt-4.1)
- Fallback: If compression fails, keeps recent messages only

**Critical Details**:
- MAX_MESSAGES = 50 pairs
- SUMMARY_THRESHOLD = 40 pairs
- `get_last_n_messages(n)`: Returns system prompt + last n complete pairs
- `n=-1`: Returns all messages (no truncation)

### TodoList Planning System

**Location**: `planning/todolist.py`

**Structure**:
```python
TodoList:
  - todolist_id: str (UUID)
  - items: List[TodoItem]
  - open_questions: List[str]  # Questions requiring user input
  - notes: str                 # Additional context

TodoItem:
  - position: int
  - description: str
  - acceptance_criteria: str   # "What done looks like" not "how to do it"
  - dependencies: List[int]    # Depends on TodoItem positions
  - status: TaskStatus         # PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
  - chosen_tool: Optional[str]
  - tool_input: Optional[Dict]
  - execution_result: Optional[Dict]
  - attempts: int (max 3)
```

**Plan Generation**:
- TodoListManager uses LLM with strict JSON schema
- Prompt includes available tools, their schemas, and mission description
- LLM generates minimal, deterministic plan with clear acceptance criteria
- Supports "ASK_USER" placeholders for missing parameters
- Plans persisted as JSON to `{work_dir}/todolists/{todolist_id}.json`

### State Persistence

**Location**: `statemanager.py`

**Features**:
- Async file I/O via `aiofiles`
- State stored as pickled dict: `{work_dir}/states/{session_id}.pkl`
- Versioning: `_version` incremented on each save, `_updated_at` timestamp
- Async locks per session to prevent race conditions
- Cleanup: `cleanup_old_states(days=7)` removes old sessions

**State Structure**:
```python
{
  "session_id": str,
  "todolist_id": Optional[str],
  "mission": str,
  "answers": Dict[str, Any],      # User responses to open_questions
  "pending_question": Optional[str],
  "_version": int,
  "_updated_at": str (ISO timestamp)
}
```

---
