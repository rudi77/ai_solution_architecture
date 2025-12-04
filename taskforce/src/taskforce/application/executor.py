"""
Application Layer - Agent Executor Service

This module provides the service layer orchestrating agent execution.
Both CLI and API entrypoints use this unified execution logic.

The AgentExecutor:
- Creates agents using AgentFactory based on profile
- Manages session lifecycle (load/create state)
- Executes agent ReAct loop
- Provides progress tracking via callbacks or streaming
- Handles comprehensive structured logging
- Provides error handling with clear messages
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Callable, Optional, List, Dict, Any

import structlog

from taskforce.application.factory import AgentFactory
from taskforce.core.domain.agent import Agent
from taskforce.core.domain.lean_agent import LeanAgent
from taskforce.core.domain.models import ExecutionResult

logger = structlog.get_logger()


@dataclass
class ProgressUpdate:
    """Progress update during execution.
    
    Represents a single event during agent execution that can be
    streamed to consumers for real-time progress tracking.
    
    Attributes:
        timestamp: When this update occurred
        event_type: Type of event (started, thought, action, observation, complete, error)
        message: Human-readable message describing the event
        details: Additional structured data about the event
    """

    timestamp: datetime
    event_type: str
    message: str
    details: dict


class AgentExecutor:
    """Service layer orchestrating agent execution.
    
    Provides unified execution logic used by both CLI and API entrypoints.
    Handles agent creation, session management, execution orchestration,
    progress tracking, and comprehensive logging.
    
    This service layer decouples the domain logic (Agent) from the
    presentation layer (CLI/API), enabling consistent behavior across
    different interfaces.
    """

    def __init__(self, factory: Optional[AgentFactory] = None):
        """Initialize AgentExecutor with optional factory.
        
        Args:
            factory: Optional AgentFactory instance. If not provided,
                    creates a default factory.
        """
        self.factory = factory or AgentFactory()
        self.logger = logger.bind(component="agent_executor")

    async def execute_mission(
        self,
        mission: str,
        profile: str = "dev",
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        use_lean_agent: bool = False,
    ) -> ExecutionResult:
        """Execute agent mission with comprehensive orchestration.
        
        Main entry point for mission execution. Orchestrates the complete
        workflow from agent creation through execution to result delivery.
        
        Workflow:
        1. Create agent using factory based on profile
        2. Generate or use provided session ID
        3. Execute agent ReAct loop with progress tracking
        4. Log execution metrics and status
        5. Return execution result
        
        Args:
            mission: Mission description (what to accomplish)
            profile: Configuration profile (dev/staging/prod)
            session_id: Optional existing session to resume
            conversation_history: Optional conversation history for chat context
            progress_callback: Optional callback for progress updates
            user_context: Optional user context for RAG security filtering
                         (user_id, org_id, scope)
            use_lean_agent: If True, use LeanAgent instead of legacy Agent.
                           LeanAgent uses native tool calling and PlannerTool.
        
        Returns:
            ExecutionResult with completion status and history
            
        Raises:
            Exception: If agent creation or execution fails
        """
        start_time = datetime.now()

        # Generate session ID if not provided
        if session_id is None:
            session_id = self._generate_session_id()

        self.logger.info(
            "mission.execution.started",
            mission=mission[:100],
            profile=profile,
            session_id=session_id,
            has_user_context=user_context is not None,
            use_lean_agent=use_lean_agent,
        )

        agent = None
        try:
            # Create agent with appropriate adapters
            agent = await self._create_agent(
                profile, user_context=user_context, use_lean_agent=use_lean_agent
            )

            # Store conversation history in state if provided
            if conversation_history:
                state = await agent.state_manager.load_state(session_id) or {}
                state["conversation_history"] = conversation_history
                await agent.state_manager.save_state(session_id, state)

            # Execute ReAct loop with progress tracking
            result = await self._execute_with_progress(
                agent=agent,
                mission=mission,
                session_id=session_id,
                progress_callback=progress_callback,
            )

            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info(
                "mission.execution.completed",
                session_id=session_id,
                status=result.status,
                duration_seconds=duration,
            )

            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()

            self.logger.error(
                "mission.execution.failed",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=duration,
            )
            raise

        finally:
            # Clean up MCP connections to avoid cancel scope errors
            if agent:
                await agent.close()

    async def execute_mission_streaming(
        self,
        mission: str,
        profile: str = "dev",
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        use_lean_agent: bool = False,
    ) -> AsyncIterator[ProgressUpdate]:
        """Execute mission with streaming progress updates.
        
        Yields ProgressUpdate objects as execution progresses, enabling
        real-time feedback to consumers (CLI progress bars, API SSE, etc).
        
        Args:
            mission: Mission description
            profile: Configuration profile (dev/staging/prod)
            session_id: Optional existing session to resume
            conversation_history: Optional conversation history for chat context
            user_context: Optional user context for RAG security filtering
            use_lean_agent: If True, use LeanAgent instead of legacy Agent
            
        Yields:
            ProgressUpdate objects for each execution event
            
        Raises:
            Exception: If agent creation or execution fails
        """
        # Generate session ID if not provided
        if session_id is None:
            session_id = self._generate_session_id()

        self.logger.info(
            "mission.streaming.started",
            mission=mission[:100],
            profile=profile,
            session_id=session_id,
            has_user_context=user_context is not None,
            use_lean_agent=use_lean_agent,
        )

        # Yield initial started event
        yield ProgressUpdate(
            timestamp=datetime.now(),
            event_type="started",
            message=f"Starting mission: {mission[:80]}",
            details={"session_id": session_id, "profile": profile, "lean": use_lean_agent},
        )

        agent = None
        try:
            # Create agent
            agent = await self._create_agent(
                profile, user_context=user_context, use_lean_agent=use_lean_agent
            )

            # Store conversation history in state if provided
            if conversation_history:
                state = await agent.state_manager.load_state(session_id) or {}
                state["conversation_history"] = conversation_history
                await agent.state_manager.save_state(session_id, state)

            # Execute with streaming
            async for update in self._execute_streaming(agent, mission, session_id):
                yield update

            self.logger.info("mission.streaming.completed", session_id=session_id)

        except Exception as e:
            self.logger.error(
                "mission.streaming.failed",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Yield error event
            yield ProgressUpdate(
                timestamp=datetime.now(),
                event_type="error",
                message=f"Execution failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            )

            raise

        finally:
            # Clean up MCP connections to avoid cancel scope errors
            if agent:
                await agent.close()

    async def _create_agent(
        self,
        profile: str,
        user_context: Optional[Dict[str, Any]] = None,
        use_lean_agent: bool = False,
    ) -> Agent | LeanAgent:
        """Create agent using factory.
        
        Creates either legacy Agent or LeanAgent based on parameters:
        - use_lean_agent=True: Creates LeanAgent (native tool calling, PlannerTool)
        - user_context provided: Creates RAG agent (legacy)
        - Otherwise: Creates standard Agent (legacy)
        
        Args:
            profile: Configuration profile name
            user_context: Optional user context for RAG security filtering
            use_lean_agent: If True, create LeanAgent instead of legacy Agent
            
        Returns:
            Agent or LeanAgent instance with injected dependencies
        """
        self.logger.debug(
            "creating_agent",
            profile=profile,
            has_user_context=user_context is not None,
            use_lean_agent=use_lean_agent,
        )
        
        # LeanAgent takes priority if requested
        if use_lean_agent:
            return await self.factory.create_lean_agent(profile=profile)
        
        # Use RAG agent factory when user_context is provided
        if user_context:
            return await self.factory.create_rag_agent(
                profile=profile, user_context=user_context
            )
        
        return await self.factory.create_agent(profile=profile)

    async def _execute_with_progress(
        self,
        agent: Agent | LeanAgent,
        mission: str,
        session_id: str,
        progress_callback: Optional[Callable[[ProgressUpdate], None]],
    ) -> ExecutionResult:
        """Execute agent with progress tracking via callback.
        
        Wraps agent execution to intercept events and send progress updates
        through the provided callback function.
        
        Args:
            agent: Agent instance to execute
            mission: Mission description
            session_id: Session identifier
            progress_callback: Optional callback for progress updates
            
        Returns:
            ExecutionResult from agent execution
        """
        # If no callback provided, execute directly
        if not progress_callback:
            return await agent.execute(mission=mission, session_id=session_id)

        # Execute agent and track progress
        # Note: Current Agent implementation doesn't support event_callback
        # For now, we execute directly and send completion update
        result = await agent.execute(mission=mission, session_id=session_id)

        # Send completion update
        progress_callback(
            ProgressUpdate(
                timestamp=datetime.now(),
                event_type="complete",
                message=result.final_message,
                details={
                    "status": result.status,
                    "session_id": result.session_id,
                    "todolist_id": result.todolist_id,
                },
            )
        )

        return result

    async def _execute_streaming(
        self, agent: Agent | LeanAgent, mission: str, session_id: str
    ) -> AsyncIterator[ProgressUpdate]:
        """Execute agent with streaming progress updates.
        
        Executes the agent and yields progress updates for each significant
        event during execution.
        
        Args:
            agent: Agent instance to execute
            mission: Mission description
            session_id: Session identifier
            
        Yields:
            ProgressUpdate objects for execution events
        """
        # Execute agent
        # Note: Current Agent implementation doesn't provide streaming
        # For now, we execute and yield updates based on result
        result = await agent.execute(mission=mission, session_id=session_id)

        # Yield updates based on execution history
        for event in result.execution_history:
            event_type = event.get("type", "unknown")
            step = event.get("step", "?")

            if event_type == "thought":
                data = event.get("data", {})
                rationale = data.get("rationale", "")
                yield ProgressUpdate(
                    timestamp=datetime.now(),
                    event_type="thought",
                    message=f"Step {step}: {rationale[:80]}",
                    details=data,
                )

            elif event_type == "observation":
                data = event.get("data", {})
                success = data.get("success", False)
                status = "success" if success else "failed"
                yield ProgressUpdate(
                    timestamp=datetime.now(),
                    event_type="observation",
                    message=f"Step {step}: {status}",
                    details=data,
                )

        # Yield final completion update
        yield ProgressUpdate(
            timestamp=datetime.now(),
            event_type="complete",
            message=result.final_message,
            details={
                "status": result.status,
                "session_id": result.session_id,
                "todolist_id": result.todolist_id,
            },
        )

    def _generate_session_id(self) -> str:
        """Generate unique session ID.
        
        Returns:
            UUID-based session identifier
        """
        return str(uuid.uuid4())

