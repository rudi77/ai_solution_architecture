# Story 1.10: Implement Application Layer - Executor Service

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.10  
**Status**: Pending  
**Priority**: Critical  
**Estimated Points**: 3  
**Dependencies**: Story 1.9 (Agent Factory)

---

## User Story

As a **developer**,  
I want **a service layer orchestrating agent execution**,  
so that **both CLI and API can use the same execution logic**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/application/executor.py` with `AgentExecutor` class
2. ✅ Implement `execute_mission(mission: str, profile: str, session_id: Optional[str]) -> ExecutionResult` method
3. ✅ Orchestration logic:
   - Use AgentFactory to create agent based on profile
   - Load or create session state
   - Execute agent ReAct loop
   - Persist state after each step
   - Handle errors and logging
4. ✅ Provide streaming progress updates via callback or async generator
5. ✅ Comprehensive structured logging for observability
6. ✅ Error handling with clear error messages
7. ✅ Unit tests with mocked factory and agent verify orchestration logic

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 execution continues independently
- **IV2: Integration Point Verification** - Executor produces same mission results as Agent V2 for identical missions
- **IV3: Performance Impact Verification** - Execution overhead from executor layer <50ms per mission

---

## Technical Notes

**AgentExecutor Implementation:**

```python
# taskforce/src/taskforce/application/executor.py
from dataclasses import dataclass
from typing import Optional, AsyncIterator, Callable
from datetime import datetime
import structlog
from taskforce.application.factory import AgentFactory
from taskforce.core.domain.agent import Agent, ExecutionResult

logger = structlog.get_logger()

@dataclass
class ProgressUpdate:
    """Progress update during execution."""
    timestamp: datetime
    event_type: str  # thought, action, observation, complete
    message: str
    details: dict

class AgentExecutor:
    """Service layer orchestrating agent execution.
    
    Provides unified execution logic used by both CLI and API entrypoints.
    """
    
    def __init__(self, factory: Optional[AgentFactory] = None):
        self.factory = factory or AgentFactory()
    
    async def execute_mission(
        self,
        mission: str,
        profile: str = "dev",
        session_id: Optional[str] = None,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None
    ) -> ExecutionResult:
        """Execute agent mission with comprehensive orchestration.
        
        Args:
            mission: Mission description
            profile: Configuration profile (dev/staging/prod)
            session_id: Optional existing session to resume
            progress_callback: Optional callback for progress updates
        
        Returns:
            ExecutionResult with completion status and history
        """
        logger.info(
            "mission.execution.started",
            mission=mission,
            profile=profile,
            session_id=session_id
        )
        
        try:
            # Create agent with appropriate adapters
            agent = self._create_agent(profile)
            
            # Generate or use provided session ID
            if session_id is None:
                session_id = self._generate_session_id()
            
            # Execute ReAct loop with progress tracking
            result = await self._execute_with_progress(
                agent=agent,
                mission=mission,
                session_id=session_id,
                progress_callback=progress_callback
            )
            
            logger.info(
                "mission.execution.completed",
                session_id=session_id,
                status=result.status,
                duration_seconds=(datetime.now() - result.started_at).total_seconds()
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "mission.execution.failed",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def execute_mission_streaming(
        self,
        mission: str,
        profile: str = "dev",
        session_id: Optional[str] = None
    ) -> AsyncIterator[ProgressUpdate]:
        """Execute mission with streaming progress updates.
        
        Yields ProgressUpdate objects as execution progresses.
        """
        agent = self._create_agent(profile)
        
        if session_id is None:
            session_id = self._generate_session_id()
        
        yield ProgressUpdate(
            timestamp=datetime.now(),
            event_type="started",
            message=f"Starting mission: {mission}",
            details={"session_id": session_id}
        )
        
        # Execute with progress streaming
        async for update in self._execute_streaming(agent, mission, session_id):
            yield update
    
    def _create_agent(self, profile: str) -> Agent:
        """Create agent using factory."""
        # Determine agent type from profile config
        # For now, default to generic agent
        return self.factory.create_agent(profile=profile)
    
    async def _execute_with_progress(
        self,
        agent: Agent,
        mission: str,
        session_id: str,
        progress_callback: Optional[Callable]
    ) -> ExecutionResult:
        """Execute agent with progress tracking."""
        
        # Wrapper to intercept agent events and send progress
        async def track_progress(event):
            if progress_callback:
                update = ProgressUpdate(
                    timestamp=datetime.now(),
                    event_type=event.type,
                    message=event.message,
                    details=event.to_dict()
                )
                progress_callback(update)
        
        # Execute agent with event tracking
        result = await agent.execute(
            mission=mission,
            session_id=session_id,
            event_callback=track_progress
        )
        
        return result
    
    async def _execute_streaming(
        self,
        agent: Agent,
        mission: str,
        session_id: str
    ) -> AsyncIterator[ProgressUpdate]:
        """Execute agent with streaming."""
        # Implement streaming execution
        ...
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return str(uuid.uuid4())
```

---

## Logging Strategy

**Structured Logs:**

```python
# Key events to log
logger.info("mission.execution.started", mission=..., profile=..., session_id=...)
logger.info("mission.thought.generated", session_id=..., thought=...)
logger.info("mission.action.selected", session_id=..., action=..., tool=...)
logger.info("mission.tool.executed", session_id=..., tool=..., duration_ms=..., success=...)
logger.info("mission.execution.completed", session_id=..., status=..., duration_seconds=...)
logger.error("mission.execution.failed", session_id=..., error=..., traceback=...)
```

---

## Testing Strategy

```python
# tests/unit/application/test_executor.py
from unittest.mock import AsyncMock, MagicMock
from taskforce.application.executor import AgentExecutor
from taskforce.application.factory import AgentFactory

@pytest.mark.asyncio
async def test_execute_mission_basic():
    # Mock factory and agent
    mock_factory = MagicMock(spec=AgentFactory)
    mock_agent = AsyncMock()
    mock_agent.execute.return_value = ExecutionResult(
        session_id="test-123",
        status="completed",
        final_message="Success"
    )
    mock_factory.create_agent.return_value = mock_agent
    
    executor = AgentExecutor(factory=mock_factory)
    result = await executor.execute_mission("Test mission", profile="dev")
    
    assert result.status == "completed"
    mock_factory.create_agent.assert_called_once_with(profile="dev")
    mock_agent.execute.assert_called_once()

@pytest.mark.asyncio
async def test_execute_mission_with_progress_callback():
    updates = []
    
    def progress_callback(update):
        updates.append(update)
    
    executor = AgentExecutor()
    result = await executor.execute_mission(
        "Test mission",
        progress_callback=progress_callback
    )
    
    # Verify progress updates were sent
    assert len(updates) > 0
    assert any(u.event_type == "thought" for u in updates)
    assert any(u.event_type == "action" for u in updates)
```

---

## Definition of Done

- [ ] AgentExecutor class implemented with execute_mission()
- [ ] Streaming execution supported via execute_mission_streaming()
- [ ] Progress callbacks implemented
- [ ] Comprehensive structured logging
- [ ] Error handling with clear messages
- [ ] Unit tests with mocked dependencies (≥80% coverage)
- [ ] Execution overhead <50ms
- [ ] Code review completed
- [ ] Code committed to version control

