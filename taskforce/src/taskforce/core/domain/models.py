"""
Core Domain Models

This module defines the core data models used throughout the agent domain.
These models represent the fundamental business entities and execution results.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """
    Result of agent execution for a mission.

    Represents the final outcome after the ReAct loop completes or pauses.
    Contains the session identifier, execution status, final message, and
    a history of all thoughts, actions, and observations.

    Attributes:
        session_id: Unique identifier for this execution session
        status: Execution status (completed, failed, pending, paused)
        final_message: Human-readable summary of execution outcome
        execution_history: List of execution events (thoughts, actions, observations)
        todolist_id: ID of the TodoList that was executed (if any)
        pending_question: Question awaiting user response (if status is paused)
    """

    session_id: str
    status: str
    final_message: str
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    todolist_id: str | None = None
    pending_question: dict[str, Any] | None = None

