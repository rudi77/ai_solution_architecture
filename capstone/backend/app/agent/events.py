"""Agent event schemas for streaming responses to frontend."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentEventType(str, Enum):
    """Event types for agent streaming responses."""
    THINKING = "agent_thinking"
    TOOL_CALL = "agent_tool_call"
    TOOL_RESULT = "agent_tool_result"
    CLARIFICATION = "agent_clarification"
    PLAN_CREATED = "agent_plan_created"
    PLAN_UPDATED = "agent_plan_updated"
    ERROR = "agent_error"
    COMPLETED = "agent_completed"
    MESSAGE = "agent_message"


class ToolCallStatus(str, Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentEvent:
    """Base agent event for streaming responses."""
    id: str
    type: AgentEventType
    message: str
    timestamp: float = field(default_factory=time.time)
    run_id: Optional[str] = field(default=None)
    conversation_id: Optional[str] = field(default=None)
    data: Optional[Dict[str, Any]] = field(default=None)


@dataclass
class AgentThinking(AgentEvent):
    """Agent reasoning/thinking event."""
    reasoning: str = field(default="")
    confidence: float = field(default=1.0)
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.THINKING
        if self.data is None:
            self.data = {}
        self.data.update({
            "reasoning": self.reasoning,
            "confidence": self.confidence
        })


@dataclass
class AgentToolCall(AgentEvent):
    """Agent tool call event."""
    tool_name: str = field(default="")
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: ToolCallStatus = field(default=ToolCallStatus.PENDING)
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.TOOL_CALL
        if self.data is None:
            self.data = {}
        self.data.update({
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "status": self.status.value
        })


@dataclass
class AgentToolResult(AgentEvent):
    """Agent tool result event."""
    tool_name: str = field(default="")
    result: Any = field(default=None)
    success: bool = field(default=True)
    error: Optional[str] = field(default=None)
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.TOOL_RESULT
        if self.data is None:
            self.data = {}
        self.data.update({
            "tool_name": self.tool_name,
            "result": self.result,
            "success": self.success,
            "error": self.error
        })


@dataclass
class AgentClarification(AgentEvent):
    """Agent clarification request event."""
    question: str = field(default="")
    context: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.CLARIFICATION
        if self.data is None:
            self.data = {}
        self.data.update({
            "question": self.question,
            "context": self.context,
            "required_fields": self.required_fields
        })


@dataclass
class AgentPlanCreated(AgentEvent):
    """Agent plan created event."""
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.PLAN_CREATED
        if self.data is None:
            self.data = {}
        self.data.update({
            "tasks": self.tasks
        })


@dataclass
class AgentMessage(AgentEvent):
    """General agent message event."""
    content: str = field(default="")
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.type = AgentEventType.MESSAGE
        if self.data is None:
            self.data = {}
        self.data.update({
            "content": self.content
        })


def create_agent_event(
    event_type: AgentEventType,
    message: str,
    event_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    **kwargs
) -> AgentEvent:
    """Factory function to create appropriate agent event based on type."""
    import uuid
    
    if event_id is None:
        event_id = f"{event_type.value}:{uuid.uuid4().hex[:8]}"
    
    base_kwargs = {
        "id": event_id,
        "message": message,
        "run_id": run_id,
        "conversation_id": conversation_id
    }
    
    if event_type == AgentEventType.THINKING:
        return AgentThinking(**base_kwargs, **kwargs)
    elif event_type == AgentEventType.TOOL_CALL:
        return AgentToolCall(**base_kwargs, **kwargs)
    elif event_type == AgentEventType.TOOL_RESULT:
        return AgentToolResult(**base_kwargs, **kwargs)
    elif event_type == AgentEventType.CLARIFICATION:
        return AgentClarification(**base_kwargs, **kwargs)
    elif event_type == AgentEventType.PLAN_CREATED:
        return AgentPlanCreated(**base_kwargs, **kwargs)
    elif event_type == AgentEventType.MESSAGE:
        return AgentMessage(**base_kwargs, **kwargs)
    else:
        return AgentEvent(type=event_type, **base_kwargs)