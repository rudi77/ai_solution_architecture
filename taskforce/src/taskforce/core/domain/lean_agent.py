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
from collections.abc import AsyncIterator
from typing import Any

import structlog

from taskforce.core.domain.models import ExecutionResult, StreamEvent
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

    async def execute_stream(
        self,
        mission: str,
        session_id: str,
    ) -> AsyncIterator[StreamEvent]:
        """
        Execute mission with streaming progress events.

        Yields StreamEvent objects as execution progresses, enabling
        real-time feedback to consumers. This is the streaming counterpart
        to execute() - same functionality but with progressive events.

        Workflow:
        1. Load state (restore PlannerTool state if exists)
        2. Build initial messages with system prompt and mission
        3. Loop: Stream LLM with tools → yield events → handle tool_calls or final content
        4. Persist state and yield final_answer event

        Args:
            mission: User's mission description
            session_id: Unique session identifier for state persistence

        Yields:
            StreamEvent objects for each significant execution event:
            - step_start: New loop iteration begins
            - llm_token: Token chunk from LLM response
            - tool_call: Tool invocation starting
            - tool_result: Tool execution completed
            - plan_updated: PlannerTool modified the plan
            - final_answer: Agent completed with final response
            - error: Error occurred during execution
        """
        self.logger.info("execute_stream_start", session_id=session_id)

        # Check if provider supports streaming
        if not hasattr(self.llm_provider, "complete_stream"):
            # Fallback: Execute normally and emit events from result
            self.logger.warning("llm_provider_no_streaming", fallback="execute")
            result = await self.execute(mission, session_id)

            # Emit events from execution history
            for event in result.execution_history:
                event_type = event.get("type", "unknown")
                if event_type == "tool_call":
                    yield StreamEvent(
                        event_type="tool_call",
                        data={
                            "tool": event.get("tool", ""),
                            "status": "completed",
                        },
                    )
                    yield StreamEvent(
                        event_type="tool_result",
                        data={
                            "tool": event.get("tool", ""),
                            "success": event.get("result", {}).get("success", False),
                            "output": self._truncate_output(
                                event.get("result", {}).get("output", "")
                            ),
                        },
                    )
                elif event_type == "final_answer":
                    yield StreamEvent(
                        event_type="final_answer",
                        data={"content": event.get("content", "")},
                    )

            # Emit final_answer if not already emitted
            if not any(
                e.get("type") == "final_answer" for e in result.execution_history
            ):
                yield StreamEvent(
                    event_type="final_answer",
                    data={"content": result.final_message},
                )
            return

        # 1. Load or initialize state
        state = await self.state_manager.load_state(session_id) or {}

        # Restore PlannerTool state if available
        if self._planner and state.get("planner_state"):
            self._planner.set_state(state["planner_state"])

        # 2. Build initial messages
        messages = self._build_initial_messages(mission, state)

        # 3. Streaming execution loop
        step = 0
        final_message = ""

        while step < self.MAX_STEPS:
            step += 1
            self.logger.info("stream_loop_step", session_id=session_id, step=step)

            # Emit step_start event
            yield StreamEvent(
                event_type="step_start",
                data={"step": step, "max_steps": self.MAX_STEPS},
            )

            # Dynamic context injection: rebuild system prompt with current plan
            current_system_prompt = self._build_system_prompt()
            messages[0] = {"role": "system", "content": current_system_prompt}

            # Stream LLM response
            tool_calls_accumulated: list[dict[str, Any]] = {}
            content_accumulated = ""

            try:
                async for chunk in self.llm_provider.complete_stream(
                    messages=messages,
                    model=self.model_alias,
                    tools=self._openai_tools,
                    tool_choice="auto",
                    temperature=0.2,
                ):
                    chunk_type = chunk.get("type")

                    if chunk_type == "token":
                        # Yield token for real-time display
                        token_content = chunk.get("content", "")
                        if token_content:
                            yield StreamEvent(
                                event_type="llm_token",
                                data={"content": token_content},
                            )
                            content_accumulated += token_content

                    elif chunk_type == "tool_call_start":
                        # Emit tool_call event when tool invocation begins
                        tc_id = chunk.get("id", "")
                        tc_name = chunk.get("name", "")
                        tc_index = chunk.get("index", 0)

                        tool_calls_accumulated[tc_index] = {
                            "id": tc_id,
                            "name": tc_name,
                            "arguments": "",
                        }

                        yield StreamEvent(
                            event_type="tool_call",
                            data={
                                "tool": tc_name,
                                "id": tc_id,
                                "status": "starting",
                            },
                        )

                    elif chunk_type == "tool_call_delta":
                        # Accumulate argument chunks
                        tc_index = chunk.get("index", 0)
                        if tc_index in tool_calls_accumulated:
                            tool_calls_accumulated[tc_index]["arguments"] += chunk.get(
                                "arguments_delta", ""
                            )

                    elif chunk_type == "tool_call_end":
                        # Update accumulated tool call with final data
                        tc_index = chunk.get("index", 0)
                        if tc_index in tool_calls_accumulated:
                            tool_calls_accumulated[tc_index]["arguments"] = chunk.get(
                                "arguments", tool_calls_accumulated[tc_index]["arguments"]
                            )

                    elif chunk_type == "error":
                        yield StreamEvent(
                            event_type="error",
                            data={"message": chunk.get("message", "Unknown error"), "step": step},
                        )

            except Exception as e:
                self.logger.error("stream_error", error=str(e), step=step)
                yield StreamEvent(
                    event_type="error",
                    data={"message": str(e), "step": step},
                )
                continue

            # Process tool calls
            if tool_calls_accumulated:
                # Convert accumulated dict to list format for message
                tool_calls_list = [
                    {
                        "id": tc_data["id"],
                        "type": "function",
                        "function": {
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"],
                        },
                    }
                    for tc_data in tool_calls_accumulated.values()
                ]

                self.logger.info(
                    "stream_tool_calls_received",
                    step=step,
                    count=len(tool_calls_list),
                    tools=[tc["function"]["name"] for tc in tool_calls_list],
                )

                # Add assistant message with tool calls to history
                messages.append(assistant_tool_calls_to_message(tool_calls_list))

                for tool_call in tool_calls_list:
                    tool_name = tool_call["function"]["name"]
                    tool_call_id = tool_call["id"]

                    # Parse arguments
                    try:
                        tool_args = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}
                        self.logger.warning(
                            "stream_tool_args_parse_failed",
                            tool=tool_name,
                            raw_args=tool_call["function"]["arguments"],
                        )

                    # Execute tool
                    tool_result = await self._execute_tool(tool_name, tool_args)

                    # Emit tool_result event
                    yield StreamEvent(
                        event_type="tool_result",
                        data={
                            "tool": tool_name,
                            "id": tool_call_id,
                            "success": tool_result.get("success", False),
                            "output": self._truncate_output(
                                tool_result.get("output", str(tool_result.get("error", "")))
                            ),
                        },
                    )

                    # Check if PlannerTool updated the plan
                    if tool_name in ("planner", "manage_plan") and tool_result.get("success"):
                        yield StreamEvent(
                            event_type="plan_updated",
                            data={"action": tool_args.get("action", "unknown")},
                        )

                    # Add tool result to messages
                    messages.append(
                        tool_result_to_message(tool_call_id, tool_name, tool_result)
                    )

            elif content_accumulated:
                # No tool calls - this is the final answer
                final_message = content_accumulated
                self.logger.info("stream_final_answer", step=step)

                yield StreamEvent(
                    event_type="final_answer",
                    data={"content": final_message},
                )
                break

            else:
                # Empty response - add prompt for LLM to continue
                self.logger.warning("stream_empty_response", step=step)
                messages.append({
                    "role": "user",
                    "content": "[System: Empty response. Please provide an answer or use a tool.]",
                })

        # Handle max steps exceeded
        if step >= self.MAX_STEPS and not final_message:
            final_message = f"Exceeded maximum steps ({self.MAX_STEPS})"
            yield StreamEvent(
                event_type="error",
                data={"message": final_message, "step": step},
            )

        # Save state
        await self._save_state(session_id, state)

        self.logger.info("execute_stream_complete", session_id=session_id, steps=step)

    def _truncate_output(self, output: str, max_length: int = 200) -> str:
        """
        Truncate output for streaming events.

        Args:
            output: The output string to truncate
            max_length: Maximum length before truncation (default: 200)

        Returns:
            Truncated string with "..." suffix if truncated.
        """
        if len(output) <= max_length:
            return output
        return output[:max_length] + "..."

    def _build_initial_messages(
        self,
        mission: str,
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Build initial message list for LLM conversation.

        Includes conversation_history from state to support multi-turn chat.
        The history contains previous user/assistant exchanges for context.

        Note: Plan status is NOT included here - it's dynamically injected
        into the system prompt on each loop iteration via _build_system_prompt().
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._base_system_prompt},
        ]

        # Load conversation history from state for multi-turn context
        conversation_history = state.get("conversation_history", [])
        if conversation_history:
            # Add previous conversation turns (user/assistant pairs)
            for msg in conversation_history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
            self.logger.debug(
                "conversation_history_loaded",
                history_length=len(conversation_history),
            )

        # Build user message with current mission and context
        user_answers = state.get("answers", {})
        answers_text = ""
        if user_answers:
            answers_text = (
                f"\n\n## User Provided Information\n"
                f"{json.dumps(user_answers, indent=2)}"
            )

        user_message = f"{mission}{answers_text}"

        # Add current mission as latest user message
        messages.append({"role": "user", "content": user_message})

        return messages

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

    async def close(self) -> None:
        """
        Clean up resources (MCP connections, etc).

        Called by CLI/API to gracefully shut down agent.
        For LeanAgent, this cleans up any MCP client contexts
        stored by the factory.
        """
        # Clean up MCP client contexts if they were attached by factory
        mcp_contexts = getattr(self, "_mcp_contexts", [])
        for ctx in mcp_contexts:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass  # Ignore cleanup errors
        self.logger.debug("agent_closed")

