# Story 1.5: Implement Infrastructure - File-Based State Manager

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.5  
**Status**: Pending  
**Priority**: High  
**Estimated Points**: 2  
**Dependencies**: Story 1.2 (Protocol Interfaces)

---

## User Story

As a **developer**,  
I want **file-based state persistence relocated from Agent V2**,  
so that **development environments don't require database setup**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/infrastructure/persistence/file_state.py`
2. ✅ Relocate code from `capstone/agent_v2/statemanager.py` with minimal changes
3. ✅ Implement `StateManagerProtocol` interface
4. ✅ Preserve all Agent V2 functionality:
   - Async file I/O (aiofiles)
   - State versioning
   - Atomic writes
   - Session directory structure (`{work_dir}/states/{session_id}.json`)
5. ✅ JSON serialization produces byte-identical output to Agent V2
6. ✅ Unit tests verify all protocol methods work correctly
7. ✅ Integration tests using actual filesystem verify state persistence and retrieval

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 `statemanager.py` remains operational (both implementations coexist)
- **IV2: Integration Point Verification** - Taskforce FileStateManager can read session files created by Agent V2
- **IV3: Performance Impact Verification** - State save/load operations match Agent V2 latency (±5%)

---

## Technical Notes

**Implementation Approach:**

```python
# taskforce/src/taskforce/infrastructure/persistence/file_state.py
import aiofiles
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from taskforce.core.interfaces.state import StateManagerProtocol

class FileStateManager:
    """File-based state persistence implementing StateManagerProtocol.
    
    Compatible with Agent V2 state files for seamless migration.
    """
    
    def __init__(self, work_dir: str = ".taskforce"):
        self.work_dir = Path(work_dir)
        self.states_dir = self.work_dir / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_state(
        self, 
        session_id: str, 
        state_data: Dict[str, Any]
    ) -> None:
        """Save session state to JSON file."""
        # Relocate logic from capstone/agent_v2/statemanager.py
        ...
    
    async def load_state(
        self, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load session state from JSON file."""
        ...
    
    async def delete_state(self, session_id: str) -> None:
        """Delete session state file."""
        ...
    
    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        ...
```

**Reference File:**
- `capstone/agent_v2/statemanager.py` - Copy/adapt this entire file

**Key Considerations:**
- Keep async file I/O patterns
- Preserve JSON format exactly (for Agent V2 compatibility)
- Maintain file versioning logic
- Keep atomic write behavior (write to temp, then rename)

---

## Testing Strategy

**Unit Tests:**
```python
# tests/unit/infrastructure/test_file_state.py
import pytest
from taskforce.infrastructure.persistence.file_state import FileStateManager

@pytest.mark.asyncio
async def test_save_and_load_state(tmp_path):
    manager = FileStateManager(work_dir=str(tmp_path))
    
    state_data = {
        "mission": "Test mission",
        "status": "in_progress",
        "answers": {}
    }
    
    await manager.save_state("test-session", state_data)
    loaded = await manager.load_state("test-session")
    
    assert loaded == state_data

@pytest.mark.asyncio
async def test_list_sessions(tmp_path):
    manager = FileStateManager(work_dir=str(tmp_path))
    
    await manager.save_state("session-1", {})
    await manager.save_state("session-2", {})
    
    sessions = await manager.list_sessions()
    
    assert "session-1" in sessions
    assert "session-2" in sessions
```

**Integration Tests:**
```python
# tests/integration/test_agent_v2_compatibility.py
async def test_read_agent_v2_state_files():
    """Verify FileStateManager can read Agent V2 state files."""
    # Copy actual Agent V2 state file to test directory
    # Load it with Taskforce FileStateManager
    # Verify data matches
    ...
```

---

## Definition of Done

- [ ] FileStateManager implements StateManagerProtocol
- [ ] All Agent V2 statemanager.py logic relocated
- [ ] Unit tests achieve ≥80% coverage
- [ ] Integration tests verify filesystem operations
- [ ] Can read Agent V2 state files (compatibility verified)
- [ ] Performance matches Agent V2 (±5%)
- [ ] Code review completed
- [ ] Code committed to version control

