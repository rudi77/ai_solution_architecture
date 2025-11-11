# Technical Debt and Known Issues

### Critical Technical Debt

#### 1. PythonTool Isolated Namespace

**Location**: `tools/code_tool.py`

**Issue**: Each PythonTool execution runs in an isolated namespace. Variables from previous steps DO NOT persist.

**Impact**:
- Agent must re-read data from files or pass via context on each call
- Increases complexity of multi-step data processing workflows
- Can cause confusion for AI agents unfamiliar with this constraint

**Workarounds** (from CLAUDE.md):
1. Pass data through `context` parameter for simple data
2. Re-read from source files (CSV, JSON) on each step
3. Agent provides hints on retry attempts after failures

**Why This Design**:
- Security: Prevents unintended side effects between executions
- Isolation: Each tool call is independent and testable
- Clean state: No accumulated globals or stale state

**Future Options**:
- Document prominently in tool description
- Add session-scoped namespace option (with explicit opt-in)
- Provide helper for persisting variables to temp files

#### 2. Windows Platform Dependency

**Issue**: PowerShellTool and various path-handling logic assumes Windows environment.

**Impact**:
- Agent platform not portable to Linux/Mac without modifications
- Tool: PowerShellTool will fail on non-Windows
- Paths: Backslash handling in file operations

**Files Affected**:
- `tools/shell_tool.py`: PowerShellTool uses Windows PowerShell
- `tools/code_tool.py`: Windows path normalization (line 60-62)
- `cli/main.py`: Windows Unicode handling (lines 24-30)

**Future Options**:
- Detect platform and use Bash/Zsh on Linux/Mac
- Unified shell tool with platform abstraction
- Pathlib usage consistently (already used in some places)

#### 3. Plugin Security Not Implemented

**Issue**: CLI plugin validation mentioned in PRD NFR5 not yet implemented.

**Location**: `cli/plugin_manager.py` - validation is TODO

**Risk**: Malicious plugins could execute arbitrary code when loaded via entry points.

**Future Requirements**:
- Plugin signature verification
- Sandboxed plugin execution
- Permission system for plugin capabilities

#### 4. Message Compression Model Hardcoded

**Location**: `agent.py:106-110` - Uses "gpt-4.1" for compression

**Issue**: Model name hardcoded instead of configurable or using agent's model.

**Impact**:
- Cannot use different provider for compression
- "gpt-4.1" may not exist in all LiteLLM configurations
- Cost optimization not possible (compression could use cheaper model)

**Future Fix**:
- Use agent's configured model or separate configurable compression model
- Add fallback logic if model unavailable

### Workarounds and Gotchas

#### Unicode Handling on Windows

**Issue**: Windows console encoding issues with Unicode

**Workaround** (implemented in `cli/main.py:24-30`):
```python
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
```

**Why Needed**: Windows console defaults to CP1252 encoding, breaks Rich output

#### TodoList JSON Schema Errors

**Issue**: LLM sometimes returns invalid JSON or wrong structure

**Workaround** (implemented in `todolist.py:89-127`):
- Graceful parsing with fallbacks to empty defaults
- Status string normalization (e.g., "inprogress" → IN_PROGRESS)
- Position defaults to index if missing

**Best Practice**: Use strict schema in prompt with examples

#### State Persistence Race Conditions

**Issue**: Multiple async operations could corrupt state file

**Workaround** (implemented in `statemanager.py:23-27`):
- Async lock per session_id
- Get-or-create pattern for locks
- State operations always wrapped in `async with lock`

#### Git Tool Windows Paths

**Issue**: Git expects forward slashes, Windows uses backslashes

**Workaround**: (Check `git_tool.py` implementation - not fully reviewed)

---
