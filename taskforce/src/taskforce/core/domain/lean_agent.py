"""
Lean Agent - Simplified ReAct Agent with Native Tool Calling

A lightweight agent implementing a single execution loop using native LLM
tool calling capabilities (OpenAI/Anthropic function calling).

Key features:
- Native tool calling (no custom JSON parsing)
- PlannerTool as first-class tool for plan management
- Dynamic context injection: plan status injected into system prompt each loop
- Robust error handling with automatic retry context
- Clean message history management

Key differences from legacy Agent:
- No TodoListManager dependency
- No QueryRouter or fast-path logic
- No ReplanStrategy
- No JSON parsing for action extraction
- Native function calling for tool invocation
"""

import json
from typing import Any

import structlog

from taskforce.core.domain.models import ExecutionResult
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.core.interfaces.state import StateManagerProtocol
from taskforce.core.interfaces.tools import ToolProtocol
from taskforce.core.prompts.autonomous_prompts import LEAN_KERNEL_PROMPT
from taskforce.core.tools.planner_tool import PlannerTool
from taskforce.infrastructure.tools.tool_converter import (
    assistant_tool_calls_to_message,
    tool_result_to_message,
    tools_to_openai_format,
)


class LeanAgent:
    """
    Lightweight ReAct agent with native tool calling.

    Implements a single execution loop using LLM native function calling:
    1. Send messages with tools to LLM
    2. If LLM returns tool_calls → execute tools, add results to history, loop
    3. If LLM returns content → that's the final answer, return

    No JSON parsing, no custom action schemas - relies entirely on native
    tool calling capabilities of modern LLMs.
    """

    MAX_STEPS = 30  # Safety limit to prevent infinite loops

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        llm_provider: LLMProviderProtocol,
        tools: list[ToolProtocol],
        system_prompt: str | None = None,
        model_alias: str = "main",
    ):
        """
        Initialize LeanAgent with injected dependencies.

        Args:
            state_manager: Protocol for session state persistence
            llm_provider: Protocol for LLM completions (must support tools parameter)
            tools: List of available tools (PlannerTool should be included)
            system_prompt: Base system prompt for LLM interactions
                          (defaults to LEAN_KERNEL_PROMPT if not provided)
            model_alias: Model alias for LLM calls (default: "main")
        """
        self.state_manager = state_manager
        self.llm_provider = llm_provider
        self._base_system_prompt = system_prompt or LEAN_KERNEL_PROMPT
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

        # Pre-convert tools to OpenAI format
        self._openai_tools = tools_to_openai_format(self.tools)

    @property
    def system_prompt(self) -> str:
        """Return base system prompt (backward compatibility)."""
        return self._base_system_prompt

    def _build_system_prompt(self) -> str:
        """
        Build system prompt with dynamic plan context injection.

        Reads current plan from PlannerTool and injects it into the system
        prompt. This ensures the LLM always has visibility into plan state
        on every loop iteration.

        Returns:
            Complete system prompt with plan context (if plan exists).
        """
        prompt = self._base_system_prompt

        # Inject current plan status if PlannerTool exists and has a plan
        if self._planner:
            plan_result = self._planner._read_plan()
            plan_output = plan_result.get("output", "")

            # Only inject if there's an actual plan (not "No active plan.")
            if plan_output and plan_output != "No active plan.":
                plan_section = (
                    "\n\n## CURRENT PLAN STATUS\n"
                    "The following plan is currently active. "
                    "Use it to guide your next steps.\n\n"
                    f"{plan_output}"
                )
                prompt += plan_section
                self.logger.debug("plan_injected", plan_steps=plan_output.count("\n") + 1)

        return prompt

    async def execute(self, mission: str, session_id: str) -> ExecutionResult:
        """
        Execute mission using native tool calling loop.

        Workflow:
        1. Load state (restore PlannerTool state if exists)
        2. Build initial messages with system prompt and mission
        3. Loop: Call LLM with tools → handle tool_calls or final content
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

        # 2. Build initial messages
        messages = self._build_initial_messages(mission, state)

        # 3. Native tool calling loop
        step = 0
        final_message = ""

        while step < self.MAX_STEPS:
            step += 1
            self.logger.info("loop_step", session_id=session_id, step=step)

            # Dynamic context injection: rebuild system prompt with current plan
            current_system_prompt = self._build_system_prompt()
            messages[0] = {"role": "system", "content": current_system_prompt}

            # Call LLM with tools
            result = await self.llm_provider.complete(
                messages=messages,
                model=self.model_alias,
                tools=self._openai_tools,
                tool_choice="auto",
                temperature=0.2,
            )

            if not result.get("success"):
                self.logger.error("llm_call_failed", error=result.get("error"))
                # Add error to history and continue (LLM can recover)
                messages.append({
                    "role": "user",
                    "content": f"[System Error: {result.get('error')}. Please try again.]",
                })
                continue

            # Check for tool calls (native tool calling)
            tool_calls = result.get("tool_calls")

            if tool_calls:
                # LLM wants to call tools
                self.logger.info(
                    "tool_calls_received",
                    step=step,
                    count=len(tool_calls),
                    tools=[tc["function"]["name"] for tc in tool_calls],
                )

                # Add assistant message with tool calls to history
                messages.append(assistant_tool_calls_to_message(tool_calls))

                # Execute each tool and add results
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_call_id = tool_call["id"]

                    # Parse arguments
                    try:
                        tool_args = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}
                        self.logger.warning(
                            "tool_args_parse_failed",
                            tool=tool_name,
                            raw_args=tool_call["function"]["arguments"],
                        )

                    # Execute tool
                    tool_result = await self._execute_tool(tool_name, tool_args)

                    # Record in execution history
                    execution_history.append({
                        "type": "tool_call",
                        "step": step,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                    })

                    # Add tool result to messages
                    messages.append(
                        tool_result_to_message(tool_call_id, tool_name, tool_result)
                    )

                    # Handle tool errors - LLM can see them and react
                    if not tool_result.get("success"):
                        self.logger.warning(
                            "tool_failed",
                            step=step,
                            tool=tool_name,
                            error=tool_result.get("error"),
                        )

            else:
                # No tool calls - LLM returned content (final answer)
                content = result.get("content", "")

                if content:
                    self.logger.info("final_answer_received", step=step)
                    final_message = content

                    execution_history.append({
                        "type": "final_answer",
                        "step": step,
                        "content": content,
                    })
                    break
                else:
                    # Empty response - unusual, but handle it
                    self.logger.warning("empty_response", step=step)
                    messages.append({
                        "role": "user",
                        "content": "[System: Your response was empty. Please provide an answer or use a tool.]",
                    })

        # 4. Determine final status
        if step >= self.MAX_STEPS and not final_message:
            status = "failed"
            final_message = f"Exceeded maximum steps ({self.MAX_STEPS})"
        else:
            status = "completed"

        # 5. Persist state
        await self._save_state(session_id, state)

        self.logger.info("execute_complete", session_id=session_id, status=status)

        return ExecutionResult(
            session_id=session_id,
            status=status,
            final_message=final_message,
            execution_history=execution_history,
        )

    def _build_initial_messages(
        self,
        mission: str,
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Build initial message list for LLM conversation.

        Note: Plan status is NOT included here - it's dynamically injected
        into the system prompt on each loop iteration via _build_system_prompt().
        """
        # Build user message with mission and context
        user_answers = state.get("answers", {})
        answers_text = ""
        if user_answers:
            answers_text = (
                f"\n\n## User Provided Information\n"
                f"{json.dumps(user_answers, indent=2)}"
            )

        user_message = f"## Mission\n{mission}{answers_text}"

        # System prompt will be rebuilt dynamically in the loop
        return [
            {"role": "system", "content": self._base_system_prompt},
            {"role": "user", "content": user_message},
        ]

    async def _execute_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool by name with given arguments."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}

        try:
            self.logger.info("tool_execute", tool=tool_name, args_keys=list(tool_args.keys()))
            result = await tool.execute(**tool_args)
            self.logger.info("tool_complete", tool=tool_name, success=result.get("success"))
            return result
        except Exception as e:
            self.logger.error("tool_exception", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def _save_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Save state including PlannerTool state."""
        if self._planner:
            state["planner_state"] = self._planner.get_state()
        await self.state_manager.save_state(session_id, state)

