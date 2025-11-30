"""
Core Agent Domain Logic

This module implements the core ReAct (Reason + Act) execution loop for the agent.
The Agent class orchestrates the execution of missions by:
1. Loading/creating TodoLists (plans)
2. Iterating through TodoItems
3. For each item: Generate Thought → Execute Action → Record Observation
4. Persisting state and plan updates

The Agent is dependency-injected with protocol interfaces, making it testable
without any infrastructure dependencies (no I/O, no external services).
"""

import json
from dataclasses import asdict
from typing import Any

import structlog

from taskforce.core.domain.events import Action, ActionType, Observation, Thought
from taskforce.core.domain.models import ExecutionResult
from taskforce.core.domain.replanning import (
    REPLAN_PROMPT_TEMPLATE,
    ReplanStrategy,
    StrategyType,
    extract_failure_context,
    validate_strategy,
)
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.core.interfaces.state import StateManagerProtocol
from taskforce.core.interfaces.todolist import (
    TaskStatus,
    TodoItem,
    TodoList,
    TodoListManagerProtocol,
)
from taskforce.core.interfaces.tools import ToolProtocol


class Agent:
    """
    Core ReAct agent with protocol-based dependencies.

    The Agent implements the ReAct (Reason + Act) execution pattern:
    1. Load state and TodoList
    2. For each pending TodoItem:
       a. Generate Thought (reasoning + action decision)
       b. Execute Action (tool call, ask user, complete, or replan)
       c. Record Observation (success/failure + result data)
    3. Update state and persist changes
    4. Repeat until all items complete or mission goal achieved

    All dependencies are injected via protocol interfaces, enabling
    pure business logic testing without infrastructure concerns.
    """

    MAX_ITERATIONS = 50  # Safety limit to prevent infinite loops

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        llm_provider: LLMProviderProtocol,
        tools: list[ToolProtocol],
        todolist_manager: TodoListManagerProtocol,
        system_prompt: str,
    ):
        """
        Initialize Agent with injected dependencies.

        Args:
            state_manager: Protocol for session state persistence
            llm_provider: Protocol for LLM completions
            tools: List of available tools implementing ToolProtocol
            todolist_manager: Protocol for TodoList management
            system_prompt: Base system prompt for LLM interactions
        """
        self.state_manager = state_manager
        self.llm_provider = llm_provider
        self.tools = {tool.name: tool for tool in tools}
        self.todolist_manager = todolist_manager
        self.system_prompt = system_prompt
        self.logger = structlog.get_logger().bind(component="agent")

    async def execute(self, mission: str, session_id: str) -> ExecutionResult:
        """
        Execute ReAct loop for given mission.

        Main entry point for agent execution. Orchestrates the complete
        ReAct cycle from mission initialization through plan execution
        to final result.

        Workflow:
        1. Load or initialize session state
        2. Create or load TodoList for mission
        3. Execute ReAct loop until completion or pause
        4. Return execution result with status and history

        Args:
            mission: User's mission description (what to accomplish)
            session_id: Unique session identifier for state persistence

        Returns:
            ExecutionResult with status, message, and execution history

        Raises:
            RuntimeError: If LLM calls fail or critical errors occur
        """
        self.logger.info("execute_start", session_id=session_id, mission=mission[:100])

        # 1. Load or initialize state
        state = await self.state_manager.load_state(session_id)
        execution_history: list[dict[str, Any]] = []

        # 2. Check if we have a completed todolist and should reset for new query
        # (Multi-turn conversation support - don't reuse completed todolists)
        if not state.get("pending_question"):  # Not answering a question
            todolist_id = state.get("todolist_id")
            if todolist_id:
                try:
                    existing_todolist = await self.todolist_manager.load_todolist(todolist_id)
                    if self._is_plan_complete(existing_todolist):
                        # Completed todolist detected - reset for new query
                        self.logger.info(
                            "completed_todolist_detected_resetting",
                            session_id=session_id,
                            old_todolist_id=todolist_id,
                        )
                        # Remove todolist reference to force creation of new one
                        state.pop("todolist_id", None)
                        await self.state_manager.save_state(session_id, state)
                except FileNotFoundError:
                    # Todolist file missing, will create new one anyway
                    self.logger.warning(
                        "todolist_file_not_found",
                        session_id=session_id,
                        todolist_id=todolist_id,
                    )

        # 3. Get or create TodoList
        todolist = await self._get_or_create_todolist(state, mission, session_id)

        # 3. Execute ReAct loop
        iteration = 0
        while not self._is_plan_complete(todolist) and iteration < self.MAX_ITERATIONS:
            iteration += 1
            self.logger.info("react_iteration", session_id=session_id, iteration=iteration)

            # Get next actionable step
            current_step = self._get_next_actionable_step(todolist)
            if not current_step:
                self.logger.info("no_actionable_steps", session_id=session_id)
                break

            self.logger.info(
                "step_start",
                session_id=session_id,
                step=current_step.position,
                description=current_step.description[:50],
            )

            # Generate Thought
            context = self._build_thought_context(current_step, todolist, state)
            # Add conversation history to context if available in state
            if state.get("conversation_history"):
                context["conversation_history"] = state.get("conversation_history")
            thought = await self._generate_thought(context)
            execution_history.append(
                {"type": "thought", "step": current_step.position, "data": asdict(thought)}
            )

            # Execute Action
            if thought.action.type == ActionType.REPLAN:
                # SPECIAL HANDLING FOR REPLAN
                self.logger.info("executing_replan", session_id=session_id)
                todolist = await self._replan(current_step, thought, todolist, state, session_id)
                
                # Create observation for history
                observation = Observation(success=True, data={"replan": "executed"})
                execution_history.append(
                    {
                        "type": "observation", 
                        "step": current_step.position, 
                        "data": asdict(observation)
                    }
                )
                
                # Restart loop to evaluate new plan
                continue
            
            else:
                # STANDARD HANDLING
                observation = await self._execute_action(thought.action, current_step, state, session_id)
            
            execution_history.append(
                {
                    "type": "observation",
                    "step": current_step.position,
                    "data": asdict(observation),
                }
            )

            # Handle observation and update step status
            await self._process_observation(
                current_step, observation, thought.action, todolist, state, session_id
            )

            # Check if we need to pause for user input
            if observation.requires_user:
                self.logger.info("execution_paused_for_user", session_id=session_id)
                pending_q = state.get("pending_question")
                return ExecutionResult(
                    session_id=session_id,
                    status="paused",
                    final_message=pending_q.get("question", "Waiting for user input") if pending_q else "Waiting for user input",
                    execution_history=execution_history,
                    todolist_id=todolist.todolist_id,
                    pending_question=pending_q,
                )

            # Check for early completion
            if thought.action.type == ActionType.COMPLETE:
                self.logger.info("early_completion", session_id=session_id)
                
                # Mark current step as completed and save summary as result
                current_step.status = TaskStatus.COMPLETED
                current_step.execution_result = {"response": thought.action.summary}
                
                # Mark remaining pending steps as skipped
                for step in todolist.items:
                    if step.status == TaskStatus.PENDING:
                        step.status = TaskStatus.SKIPPED
                
                await self.todolist_manager.update_todolist(todolist)
                await self.state_manager.save_state(session_id, state)

                return ExecutionResult(
                    session_id=session_id,
                    status="completed",
                    final_message=thought.action.summary or "Mission completed",
                    execution_history=execution_history,
                    todolist_id=todolist.todolist_id,
                )

        # 4. Determine final status and extract final message
        if self._is_plan_complete(todolist):
            status = "completed"
            # Try to extract meaningful response from last completed step
            final_message = self._extract_final_message(todolist, execution_history)
        elif iteration >= self.MAX_ITERATIONS:
            status = "failed"
            final_message = f"Exceeded maximum iterations ({self.MAX_ITERATIONS})"
        else:
            status = "failed"
            final_message = "Execution stopped with incomplete tasks"

        self.logger.info("execute_complete", session_id=session_id, status=status)

        return ExecutionResult(
            session_id=session_id,
            status=status,
            final_message=final_message,
            execution_history=execution_history,
            todolist_id=todolist.todolist_id,
        )

    async def _replan(
        self, current_step: TodoItem, thought: Thought, todolist: TodoList, state: dict[str, Any], session_id: str
    ) -> TodoList:
        """
        Intelligent Replanning: Modifies the plan based on failure context.
        """
        self.logger.info("replanning_start", session_id=session_id, step=current_step.position)
        
        # 1. Ask LLM for a recovery strategy
        strategy = await self._generate_replan_strategy(current_step, todolist)
        
        if not strategy:
             self.logger.warning("replan_failed_no_strategy", session_id=session_id)
             # Fallback to skip if strategy generation failed
             current_step.status = TaskStatus.SKIPPED
             await self.todolist_manager.update_todolist(todolist)
             return todolist

        self.logger.info("replan_strategy_selected", 
                        session_id=session_id, 
                        type=strategy.strategy_type.value,
                        reasoning=strategy.rationale)

        # 2. Apply the strategy to the TodoList entity (In-Memory)
        if strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS:
            # Modify the current step (e.g. clarify description or criteria)
            new_params = strategy.modifications.get("new_parameters", {})
            if new_params:
                 current_step.tool_input = new_params
            current_step.status = TaskStatus.PENDING # Reset status
            current_step.replan_count += 1
            
        elif strategy.strategy_type == StrategyType.SWAP_TOOL:
             current_step.chosen_tool = strategy.modifications.get("new_tool")
             current_step.tool_input = strategy.modifications.get("new_parameters", {})
             current_step.status = TaskStatus.PENDING
             current_step.replan_count += 1
             
        elif strategy.strategy_type == StrategyType.DECOMPOSE_TASK:
            # Replace current step with multiple smaller steps
            new_items = []
            start_pos = current_step.position
            
            # Create new sub-items
            subtasks = strategy.modifications.get("subtasks", [])
            for i, item_data in enumerate(subtasks):
                new_item = TodoItem(
                    position=start_pos + i,
                    description=item_data["description"],
                    acceptance_criteria=item_data["acceptance_criteria"],
                    dependencies=current_step.dependencies, # Inherit dependencies
                    status=TaskStatus.PENDING
                )
                new_items.append(new_item)
            
            if new_items:
                # Remove old item and insert new ones
                # We need to shift positions of all subsequent items
                shift_offset = len(new_items) - 1
                
                # 1. Remove current
                if current_step in todolist.items:
                    todolist.items.remove(current_step)
                
                # 2. Shift subsequent items
                for item in todolist.items:
                    if item.position > start_pos:
                        item.position += shift_offset
                        
                # 3. Add new items
                todolist.items.extend(new_items)
                todolist.items.sort(key=lambda x: x.position)
            
        elif strategy.strategy_type == StrategyType.SKIP:
            current_step.status = TaskStatus.SKIPPED
            
        # 3. Persist the modified plan
        await self.todolist_manager.update_todolist(todolist)
        
        return todolist

    async def _generate_replan_strategy(
        self, current_step: TodoItem, todolist: TodoList
    ) -> ReplanStrategy | None:
        """
        Asks the LLM how to fix the broken plan.
        """
        # Context building
        context = extract_failure_context(current_step)
        context["available_tools"] = self._get_tools_description()
        
        # Render prompt
        user_prompt = REPLAN_PROMPT_TEMPLATE.format(**context)
        
        result = await self.llm_provider.complete(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="main", # Use the smart model for replanning
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        if not result.get("success"):
            self.logger.error("replan_llm_failed", error=result.get("error"))
            return None
            
        try:
            data = json.loads(result["content"])
            strategy = ReplanStrategy.from_dict(data)
            
            if validate_strategy(strategy, self.logger):
                return strategy
            else:
                self.logger.warning("invalid_replan_strategy", strategy=data)
                return None
                
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("replan_parse_failed", error=str(e), content=result["content"])
            return None

    async def _get_or_create_todolist(
        self, state: dict[str, Any], mission: str, session_id: str
    ) -> TodoList:
        """Get existing TodoList or create new one."""
        todolist_id = state.get("todolist_id")

        if todolist_id:
            try:
                todolist = await self.todolist_manager.load_todolist(todolist_id)
                
                # --- FIX START: Prüfen, ob die Liste schon fertig ist ---
                # Wir prüfen, ob alle Items den Status COMPLETED haben (oder SKIPPED)
                all_items_done = all(
                    item.status.value in ["COMPLETED", "SKIPPED"] 
                    for item in todolist.items
                )

                # Wenn die Liste noch NICHT fertig ist, machen wir damit weiter.
                # (Das passiert z.B., wenn der Agent mehrere Steps nacheinander macht)
                if not all_items_done:
                    self.logger.info("todolist_loaded_resuming", session_id=session_id, todolist_id=todolist_id)
                    return todolist
                
                # Wenn die Liste fertig IST, bedeutet der neue User-Input eine NEUE Mission.
                # Wir ignorieren die alte Liste und lassen den Code unten eine neue erstellen.
                self.logger.info("todolist_completed_starting_new_mission", session_id=session_id, old_id=todolist_id)
                
                # Optional: State bereinigen, damit wir sauber starten
                # state["todolist_id"] = None 
                
                # --- FIX END ---

            except FileNotFoundError:
                self.logger.warning(
                    "todolist_not_found", session_id=session_id, todolist_id=todolist_id
                )

        # Create new TodoList (Wird ausgeführt, wenn keine ID da ist ODER die alte Liste fertig war)
        self.logger.info("creating_new_todolist_for_mission", mission=mission)
        
        tools_desc = self._get_tools_description()
        
        # WICHTIG: Wenn wir eine neue Mission starten, sollten wir evtl. 
        # alte "answers" nicht blind übernehmen, es sei denn, es sind persistente Fakten.
        # Für diesen Fix lassen wir es erstmal so.
        answers = state.get("answers", {})
        
        todolist = await self.todolist_manager.create_todolist(
            mission=mission, tools_desc=tools_desc, answers=answers
        )

        state["todolist_id"] = todolist.todolist_id
        await self.state_manager.save_state(session_id, state)

        self.logger.info(
            "todolist_created",
            session_id=session_id,
            todolist_id=todolist.todolist_id,
            items=len(todolist.items),
        )

        return todolist

    def _get_tools_description(self) -> str:
        """Build formatted description of available tools."""
        descriptions = []
        for tool in self.tools.values():
            params = json.dumps(tool.parameters_schema, indent=2)
            descriptions.append(f"Tool: {tool.name}\nDescription: {tool.description}\nParameters: {params}")
        return "\n\n".join(descriptions)

    def _get_next_actionable_step(self, todolist: TodoList) -> TodoItem | None:
        """Find next step that can be executed."""
        for step in sorted(todolist.items, key=lambda s: s.position):
            # Skip completed steps
            if step.status == TaskStatus.COMPLETED:
                continue

            # Check if pending with dependencies met
            if step.status == TaskStatus.PENDING:
                deps_met = all(
                    any(s.position == dep and s.status == TaskStatus.COMPLETED for s in todolist.items)
                    for dep in step.dependencies
                )
                if deps_met:
                    return step

            # Check if failed but has retries remaining
            if step.status == TaskStatus.FAILED and step.attempts < step.max_attempts:
                return step

        return None

    def _build_thought_context(
        self, step: TodoItem, todolist: TodoList, state: dict[str, Any]
    ) -> dict[str, Any]:
        """Build context for thought generation."""
        # Collect results from previous steps
        previous_results = [
            {
                "step": s.position,
                "description": s.description,
                "tool": s.chosen_tool,
                "result": s.execution_result,
                "status": s.status.value,
            }
            for s in todolist.items
            if s.execution_result and s.position < step.position
        ]

        # Extract error from current step if this is a retry
        current_error = None
        if step.execution_result and not step.execution_result.get("success"):
            current_error = {
                "error": step.execution_result.get("error"),
                "type": step.execution_result.get("type"),
                "hints": step.execution_result.get("hints", []),
                "attempt": step.attempts,
                "max_attempts": step.max_attempts,
            }

        return {
            "current_step": step,
            "current_error": current_error,
            "previous_results": previous_results[-5:],  # Last 5 results
            "available_tools": self._get_tools_description(),
            "user_answers": state.get("answers", {}),
        }

    async def _generate_thought(self, context: dict[str, Any]) -> Thought:
        """Generate thought using LLM."""
        current_step = context["current_step"]

        # Build prompt
        schema_hint = {
            "step_ref": "int",
            "rationale": "string (<= 2 sentences)",
            "action": {
                "type": "tool_call|ask_user|complete|replan|finish_step",
                "tool": "string|null (for tool_call)",
                "tool_input": "object (for tool_call)",
                "question": "string (for ask_user)",
                "answer_key": "string (for ask_user)",
                "summary": "string (for complete)",
            },
            "expected_outcome": "string",
            "confidence": "float (0-1, optional)",
        }

        # Build error context if retry
        error_context = ""
        if context.get("current_error"):
            error = context["current_error"]
            error_context = f"""
PREVIOUS ATTEMPT FAILED (Attempt {error['attempt']}/{error['max_attempts']}):
Error Type: {error.get('type', 'Unknown')}
Error Message: {error.get('error', 'Unknown error')}
"""
            if error.get("hints"):
                error_context += "\nHints to fix:\n"
                for hint in error["hints"]:
                    error_context += f"  - {hint}\n"
            
            # Add hint to replan if persistent failure
            error_context += "\nIf the error persists or the tool is unsuitable, choose 'replan' action to modify the task structure.\n"

        user_prompt = (
            "You are the ReAct Execution Agent.\n"
            "Analyze the current step and choose the best action.\n\n"
            f"CURRENT_STEP:\n{json.dumps(asdict(current_step), indent=2)}\n\n"
            f"{error_context}"
            f"PREVIOUS_RESULTS:\n{json.dumps(context.get('previous_results', []), indent=2)}\n\n"
            f"USER_ANSWERS:\n{json.dumps(context.get('user_answers', {}), indent=2)}\n\n"
            f"AVAILABLE_TOOLS:\n{context.get('available_tools', '')}\n\n"
            "Rules:\n"
            "- Choose the appropriate tool to fulfill the step's acceptance criteria.\n"
            "- If this is a retry, FIX the previous error using the hints provided.\n"
            "- If information is missing, use ask_user action.\n"
            "- If the entire mission is already fulfilled, use complete action.\n"
            "- IMPORTANT: After a tool succeeds, you may continue iterating (e.g., run tests).\n"
            "  Only use finish_step when you have VERIFIED the step's acceptance criteria are met.\n"
            "- Return STRICT JSON only matching this schema:\n"
            f"{json.dumps(schema_hint, indent=2)}\n"
        )

        # Build messages with optional conversation history
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history if available in context
        conversation_history = context.get("conversation_history")
        if conversation_history:
            # Filter out system messages from history (we already have one)
            for msg in conversation_history:
                if msg.get("role") != "system":
                    messages.append(msg)
        
        # Add current user prompt
        messages.append({"role": "user", "content": user_prompt})

        self.logger.info("llm_call_thought_start", step=current_step.position)

        result = await self.llm_provider.complete(
            messages=messages, model="main", response_format={"type": "json_object"}, temperature=0.2
        )

        if not result.get("success"):
            self.logger.error(
                "thought_generation_failed", step=current_step.position, error=result.get("error")
            )
            raise RuntimeError(f"LLM completion failed: {result.get('error')}")

        raw_content = result["content"]
        self.logger.info("llm_call_thought_end", step=current_step.position)

        # Parse thought from JSON
        try:
            data = json.loads(raw_content)
            action_data = data["action"]
            action = Action(
                type=ActionType(action_data["type"]),
                tool=action_data.get("tool"),
                tool_input=action_data.get("tool_input"),
                question=action_data.get("question"),
                answer_key=action_data.get("answer_key"),
                summary=action_data.get("summary"),
                replan_reason=action_data.get("replan_reason"),
            )
            thought = Thought(
                step_ref=data["step_ref"],
                rationale=data["rationale"],
                action=action,
                expected_outcome=data["expected_outcome"],
                confidence=data.get("confidence", 1.0),
            )
            return thought
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(
                "thought_parse_failed",
                step=current_step.position,
                error=str(e),
                raw_content=raw_content[:500],
            )
            raise RuntimeError(f"Failed to parse thought: {e}") from e

    async def _execute_action(
        self, action: Action, step: TodoItem, state: dict[str, Any], session_id: str
    ) -> Observation:
        """Execute action and return observation."""
        if action.type == ActionType.TOOL_CALL:
            return await self._execute_tool(action, step)

        elif action.type == ActionType.ASK_USER:
            # Store pending question in state
            answer_key = action.answer_key or f"step_{step.position}_q{step.attempts}"
            state["pending_question"] = {
                "answer_key": answer_key,
                "question": action.question,
                "for_step": step.position,
            }
            await self.state_manager.save_state(session_id, state)

            return Observation(
                success=True,
                data={"question": action.question, "answer_key": answer_key},
                requires_user=True,
            )

        elif action.type == ActionType.COMPLETE:
            return Observation(success=True, data={"summary": action.summary})

        elif action.type == ActionType.REPLAN:
            # Replanning would be handled by todolist_manager
            return Observation(success=True, data={"replan_reason": action.replan_reason})

        elif action.type == ActionType.FINISH_STEP:
            # Explicit signal that agent has verified and completed the step
            return Observation(success=True, data={"finish_step": True})

        else:
            return Observation(success=False, error=f"Unknown action type: {action.type}")

    async def _execute_tool(self, action: Action, step: TodoItem) -> Observation:
        """Execute tool and return observation."""
        tool = self.tools.get(action.tool)
        if not tool:
            return Observation(success=False, error=f"Tool not found: {action.tool}")

        try:
            self.logger.info("tool_execution_start", tool=action.tool, step=step.position)
            result = await tool.execute(**(action.tool_input or {}))
            self.logger.info("tool_execution_end", tool=action.tool, step=step.position)

            return Observation(success=result.get("success", False), data=result, error=result.get("error"))
        except Exception as e:
            self.logger.error("tool_execution_exception", tool=action.tool, error=str(e))
            return Observation(success=False, error=str(e))

    async def _process_observation(
        self,
        step: TodoItem,
        observation: Observation,
        action: Action,
        todolist: TodoList,
        state: dict[str, Any],
        session_id: str,
    ) -> None:
        """
        Process observation and update step status.

        Key behavior: Tool success does NOT auto-complete a step. The agent must
        explicitly emit FINISH_STEP to mark a step as completed. This allows
        the agent to iterate (e.g., run tests after writing code) and self-heal
        errors before declaring the task done.
        """
        # Update step with execution details (only set tool/input if action has them)
        if action.tool:
            step.chosen_tool = action.tool
            step.tool_input = action.tool_input
        step.execution_result = observation.data
        step.attempts += 1

        # Initialize execution history if needed
        if step.execution_history is None:
            step.execution_history = []

        # Track execution history
        step.execution_history.append(
            {
                "tool": action.tool,
                "success": observation.success,
                "error": observation.error,
                "attempt": step.attempts,
            }
        )

        # Update status based on action type and observation
        if action.type == ActionType.FINISH_STEP:
            # Explicit completion signal from agent
            step.status = TaskStatus.COMPLETED
            self.logger.info(
                "step_completed_explicitly",
                session_id=session_id,
                step=step.position,
                total_attempts=step.attempts,
            )
        elif observation.success:
            # Tool succeeded but step is NOT complete - agent must continue iterating
            step.status = TaskStatus.PENDING
            step.attempts = 0  # Reset attempts for extended workflows
            self.logger.info(
                "tool_success_continuing_iteration",
                session_id=session_id,
                step=step.position,
                tool=action.tool,
            )
        else:
            # Tool execution failed
            if step.attempts >= step.max_attempts:
                step.status = TaskStatus.FAILED
                self.logger.error("step_exhausted", session_id=session_id, step=step.position)
            else:
                # Reset to PENDING for retry
                step.status = TaskStatus.PENDING
                self.logger.info(
                    "retry_step", session_id=session_id, step=step.position, attempt=step.attempts
                )

        # Persist changes
        await self.todolist_manager.update_todolist(todolist)
        await self.state_manager.save_state(session_id, state)

    def _is_plan_complete(self, todolist: TodoList) -> bool:
        """Check if all steps are completed or skipped."""
        return all(s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for s in todolist.items)

    def _extract_final_message(
        self, todolist: TodoList, execution_history: list[dict[str, Any]]
    ) -> str:
        """
        Extract meaningful final message from completed plan.

        Tries to find the actual response/result from the last completed step,
        rather than just returning "All tasks completed successfully".

        Args:
            todolist: Completed TodoList
            execution_history: Execution history with thoughts and observations

        Returns:
            Meaningful final message or default completion message
        """
        # Try to find the last completed step's result
        for step in reversed(todolist.items):
            if step.status == TaskStatus.COMPLETED and step.execution_result:
                result = step.execution_result
                
                # Debug logging
                self.logger.debug(
                    "extracting_final_message",
                    step_position=step.position,
                    result_type=type(result).__name__,
                    result_keys=list(result.keys()) if isinstance(result, dict) else None,
                )
                
                # If it's a tool result with generated text (e.g., llm_generate)
                if isinstance(result, dict):
                    # Check for common result fields
                    if "generated_text" in result:
                        text = result["generated_text"]
                        if text and isinstance(text, str) and len(text.strip()) > 0:
                            return text.strip()
                    if "response" in result:
                        text = result["response"]
                        if text and isinstance(text, str) and len(text.strip()) > 0:
                            return text.strip()
                    if "content" in result:
                        text = result["content"]
                        if text and isinstance(text, str) and len(text.strip()) > 0:
                            return text.strip()
                    if "result" in result and isinstance(result["result"], str):
                        text = result["result"]
                        if text and len(text.strip()) > 0:
                            return text.strip()
                    
                    # For successful tool executions, try to extract meaningful data
                    if result.get("success") and "data" in result:
                        data = result["data"]
                        if isinstance(data, dict):
                            if "generated_text" in data:
                                text = data["generated_text"]
                                if text and isinstance(text, str) and len(text.strip()) > 0:
                                    return text.strip()
                            if "response" in data:
                                text = data["response"]
                                if text and isinstance(text, str) and len(text.strip()) > 0:
                                    return text.strip()
                            if "content" in data:
                                text = data["content"]
                                if text and isinstance(text, str) and len(text.strip()) > 0:
                                    return text.strip()

        # Fallback: return default message
        return "All tasks completed successfully"
