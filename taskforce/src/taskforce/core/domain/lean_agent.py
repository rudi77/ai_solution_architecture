"""
Lean Agent - Simplified ReAct Agent

A lightweight agent implementing a single execution loop.
Replaces the complex Plan-and-Execute state machine with flexible,
LLM-controlled planning via PlannerTool.

Key differences from legacy Agent:
- No TodoListManager dependency
- No QueryRouter or fast-path logic
- No ReplanStrategy
- Single execution loop (no _execute_fast_path vs _execute_full_path)
- PlannerTool as first-class tool for plan management
"""

import json
from dataclasses import asdict
from typing import Any

import structlog

from taskforce.core.domain.events import Action, ActionType, Observation, Thought
from taskforce.core.domain.models import ExecutionResult
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.core.interfaces.state import StateManagerProtocol
from taskforce.core.interfaces.tools import ToolProtocol
from taskforce.core.tools.planner_tool import PlannerTool


class LeanAgent:
    """
    Lightweight ReAct agent with PlannerTool-based planning.

    Implements a single execution loop where the LLM decides:
    1. When to create/update the plan (via PlannerTool)
    2. Which tools to use for task execution
    3. When to respond with the final answer

    No legacy TodoListManager, QueryRouter, or ReplanStrategy.
    Plan state is managed by PlannerTool and persisted via StateManager.
    """

    MAX_STEPS = 30  # Safety limit to prevent infinite loops

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        llm_provider: LLMProviderProtocol,
        tools: list[ToolProtocol],
        system_prompt: str,
        model_alias: str = "main",
    ):
        """
        Initialize LeanAgent with injected dependencies.

        Args:
            state_manager: Protocol for session state persistence
            llm_provider: Protocol for LLM completions
            tools: List of available tools (PlannerTool should be included)
            system_prompt: Base system prompt for LLM interactions
            model_alias: Model alias for LLM calls (default: "main")
        """
        self.state_manager = state_manager
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt
        self.model_alias = model_alias
        self.logger = structlog.get_logger().bind(component="lean_agent")

        # Build tools dict, ensure PlannerTool exists
        self.tools: dict[str, ToolProtocol] = {}
        self._planner: PlannerTool | None = None

        for tool in tools:
            self.tools[tool.name] = tool
            if isinstance(tool, PlannerTool):
                self._planner = tool

        # Create PlannerTool if not provided
        if self._planner is None:
            self._planner = PlannerTool()
            self.tools[self._planner.name] = self._planner

    async def execute(self, mission: str, session_id: str) -> ExecutionResult:
        """
        Execute mission using single ReAct loop.

        Workflow:
        1. Load state (restore PlannerTool state if exists)
        2. Build initial context with mission
        3. Loop: Think → Act → Observe until done or MAX_STEPS
        4. Persist state and return result

        Args:
            mission: User's mission description
            session_id: Unique session identifier for state persistence

        Returns:
            ExecutionResult with status and final message
        """
        self.logger.info("execute_start", session_id=session_id, mission=mission[:100])

        # 1. Load or initialize state
        state = await self.state_manager.load_state(session_id) or {}
        execution_history: list[dict[str, Any]] = []

        # Restore PlannerTool state if available
        if self._planner and state.get("planner_state"):
            self._planner.set_state(state["planner_state"])

        # 2. Execute single loop
        step = 0
        final_message = ""

        while step < self.MAX_STEPS:
            step += 1
            self.logger.info("loop_step", session_id=session_id, step=step)

            # 2a. Generate thought (LLM decides action)
            context = self._build_context(mission, execution_history, state)
            thought = await self._generate_thought(context)

            execution_history.append({
                "type": "thought",
                "step": step,
                "data": asdict(thought),
            })

            # 2b. Execute action
            observation = await self._execute_action(thought.action, state, session_id)

            execution_history.append({
                "type": "observation",
                "step": step,
                "data": asdict(observation),
            })

            # 2c. Check for completion
            if thought.action.type == ActionType.RESPOND:
                final_message = thought.action.summary or "Task completed."
                break

            if thought.action.type == ActionType.ASK_USER:
                # Pause execution for user input
                state["pending_question"] = {
                    "question": thought.action.question,
                    "answer_key": thought.action.answer_key,
                }
                await self._save_state(session_id, state)

                return ExecutionResult(
                    session_id=session_id,
                    status="paused",
                    final_message=thought.action.question or "Awaiting input",
                    execution_history=execution_history,
                    pending_question=state["pending_question"],
                )

            # 2d. Handle tool failure (continue loop, LLM can retry)
            if not observation.success:
                self.logger.warning(
                    "tool_failed",
                    step=step,
                    tool=thought.action.tool,
                    error=observation.error,
                )

        # 3. Determine final status
        if step >= self.MAX_STEPS and not final_message:
            status = "failed"
            final_message = f"Exceeded maximum steps ({self.MAX_STEPS})"
        else:
            status = "completed"

        # 4. Persist state
        await self._save_state(session_id, state)

        self.logger.info("execute_complete", session_id=session_id, status=status)

        return ExecutionResult(
            session_id=session_id,
            status=status,
            final_message=final_message,
            execution_history=execution_history,
        )

    def _build_context(
        self,
        mission: str,
        execution_history: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Build context for LLM thought generation."""
        # Get current plan from PlannerTool
        plan_status = "No plan created yet."
        if self._planner:
            result = self._planner._read_plan()
            plan_status = result.get("output", "No plan created yet.")

        # Extract recent history (last 5 steps)
        recent_history = execution_history[-10:] if execution_history else []

        return {
            "mission": mission,
            "plan_status": plan_status,
            "recent_history": recent_history,
            "user_answers": state.get("answers", {}),
            "available_tools": list(self.tools.keys()),
        }

    async def _generate_thought(self, context: dict[str, Any]) -> Thought:
        """Generate thought using LLM."""
        # Minimal schema hint
        schema_hint = {
            "action": "tool_call | respond | ask_user",
            "tool": "string (required for tool_call)",
            "tool_input": "object (required for tool_call)",
            "question": "string (required for ask_user)",
            "answer_key": "string (required for ask_user)",
            "summary": "string (required for respond)",
        }

        user_prompt = (
            f"## Mission\n{context['mission']}\n\n"
            f"## Current Plan\n{context['plan_status']}\n\n"
            f"## Recent History\n{json.dumps(context['recent_history'], indent=2)}\n\n"
            f"## Available Tools\n{', '.join(context['available_tools'])}\n\n"
            "## Instructions\n"
            "1. If no plan exists, use the 'planner' tool to create one.\n"
            "2. Execute tasks using appropriate tools.\n"
            "3. Mark tasks done with 'planner' tool after completion.\n"
            "4. When all tasks are done, use 'respond' action with summary.\n\n"
            f"Return JSON matching: {json.dumps(schema_hint)}"
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = await self.llm_provider.complete(
            messages=messages,
            model=self.model_alias,
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        if not result.get("success"):
            self.logger.error("thought_generation_failed", error=result.get("error"))
            # Return respond action as fallback
            return Thought(
                action=Action(
                    type=ActionType.RESPOND,
                    summary="An error occurred during processing.",
                )
            )

        return self._parse_thought(result["content"])

    def _parse_thought(self, raw_content: str) -> Thought:
        """Parse LLM response into Thought object."""
        try:
            data = json.loads(raw_content)

            action_type_raw = data.get("action", "respond")

            # Normalize legacy action types
            if action_type_raw == "finish_step":
                action_type_raw = "respond"

            # Fallback: if action looks like tool name
            valid_types = {a.value for a in ActionType}
            if action_type_raw not in valid_types:
                if data.get("tool") or data.get("tool_input"):
                    action_type_raw = "tool_call"
                else:
                    action_type_raw = "respond"

            action = Action(
                type=ActionType(action_type_raw),
                tool=data.get("tool"),
                tool_input=data.get("tool_input"),
                question=data.get("question"),
                answer_key=data.get("answer_key"),
                summary=data.get("summary"),
            )

            return Thought(action=action)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning("thought_parse_failed", error=str(e))
            return Thought(
                action=Action(
                    type=ActionType.RESPOND,
                    summary="Failed to parse response. Please try again.",
                )
            )

    async def _execute_action(
        self,
        action: Action,
        state: dict[str, Any],
        session_id: str,
    ) -> Observation:
        """Execute action and return observation."""
        if action.type == ActionType.TOOL_CALL:
            return await self._execute_tool(action)

        elif action.type == ActionType.ASK_USER:
            return Observation(
                success=True,
                data={"question": action.question, "answer_key": action.answer_key},
                requires_user=True,
            )

        elif action.type == ActionType.RESPOND:
            return Observation(success=True, data={"summary": action.summary})

        else:
            return Observation(success=False, error=f"Unknown action: {action.type}")

    async def _execute_tool(self, action: Action) -> Observation:
        """Execute a tool and return observation."""
        tool = self.tools.get(action.tool)
        if not tool:
            return Observation(success=False, error=f"Tool not found: {action.tool}")

        tool_input = action.tool_input or {}

        try:
            self.logger.info("tool_execute", tool=action.tool)
            result = await tool.execute(**tool_input)
            self.logger.info("tool_complete", tool=action.tool, success=result.get("success"))

            return Observation(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
            )
        except Exception as e:
            self.logger.error("tool_exception", tool=action.tool, error=str(e))
            return Observation(success=False, error=str(e))

    async def _save_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Save state including PlannerTool state."""
        if self._planner:
            state["planner_state"] = self._planner.get_state()
        await self.state_manager.save_state(session_id, state)

    def _get_tools_description(self) -> str:
        """Build formatted description of available tools."""
        descriptions = []
        for tool in self.tools.values():
            params = json.dumps(tool.parameters_schema, indent=2)
            descriptions.append(
                f"Tool: {tool.name}\n"
                f"Description: {tool.description}\n"
                f"Parameters: {params}"
            )
        return "\n\n".join(descriptions)

