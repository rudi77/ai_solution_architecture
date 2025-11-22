"""
Domain Events for Agent Execution

This module defines the core domain events that occur during agent execution.
Events represent immutable facts about what happened during the ReAct loop:
- Thought: Agent's reasoning and action decision
- Action: The specific action to be executed
- Observation: The result of executing an action

These events form the backbone of the ReAct (Reason + Act) execution pattern.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """Type of action the agent can take."""

    TOOL_CALL = "tool_call"
    ASK_USER = "ask_user"
    COMPLETE = "complete"
    REPLAN = "replan"


@dataclass
class Action:
    """
    An action to be executed by the agent.

    Represents the agent's decision about what to do next in the ReAct loop.
    The action type determines which fields are relevant:
    - tool_call: Requires tool and tool_input
    - ask_user: Requires question and answer_key
    - complete: Requires summary
    - replan: Requires replan_reason

    Attributes:
        type: Type of action (tool_call, ask_user, complete, replan)
        tool: Tool name to execute (for tool_call)
        tool_input: Parameters for tool execution (for tool_call)
        question: Question to ask user (for ask_user)
        answer_key: Stable identifier for user answer (for ask_user)
        summary: Final summary message (for complete)
        replan_reason: Reason for replanning (for replan)
    """

    type: ActionType
    tool: str | None = None
    tool_input: dict[str, Any] | None = None
    question: str | None = None
    answer_key: str | None = None
    summary: str | None = None
    replan_reason: str | None = None


@dataclass
class Thought:
    """
    Agent's reasoning about the current step.

    Represents the "Reason" part of the ReAct loop. The agent analyzes
    the current state, considers available tools and context, and decides
    what action to take next.

    Attributes:
        step_ref: Reference to TodoItem position being executed
        rationale: Brief explanation of reasoning (max 2-3 sentences)
        action: The action decided upon
        expected_outcome: What the agent expects to happen after action
        confidence: Confidence level in this decision (0.0-1.0)
    """

    step_ref: int
    rationale: str
    action: Action
    expected_outcome: str
    confidence: float = 1.0


@dataclass
class Observation:
    """
    Result of executing an action.

    Represents the "Act" part of the ReAct loop. After executing an action,
    the agent observes the result and uses it to inform the next thought.

    Attributes:
        success: Whether the action succeeded
        data: Result data from action execution (tool output, user answer, etc.)
        error: Error message if action failed
        requires_user: Whether execution is paused waiting for user input
    """

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    requires_user: bool = False

