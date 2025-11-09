# An Agent class

from dataclasses import field, asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, AsyncIterator, Dict, List, Optional
import uuid
# Removed: from attr import asdict, dataclass - using dataclasses instead
import litellm
import structlog

from capstone.agent_v2.planning.todolist import TaskStatus, TodoItem, TodoList, TodoListManager
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool

GENERIC_SYSTEM_PROMPT = """
You are a ReAct-style execution agent.

## Core Principles
- **Plan First**: Always build or refine a Todo List before executing. Plans must be minimal, deterministic, and single-responsibility (each step has one clear outcome).
- **Clarify Early**: If any required parameter is unknown, mark it as "ASK_USER" and add a precise clarification question to open_questions. Do not guess.
- **Determinism & Minimalism**: Prefer fewer, well-scoped steps over many fuzzy ones. Outputs must be concise, structured, and directly actionable. No filler text.
- **Tool Preference**: Use available tools whenever possible. Only ask the user when essential data is missing. Never hallucinate tools.
- **State Updates**: After every tool call or user clarification, update state (Todo List, step status, answers). Avoid infinite loops.
- **Stop Condition**: End execution when the mission’s acceptance criteria are met or all Todo steps are completed.

## Decision Policy
- Prefer tools > ask_user > stop.
- Never assume implicit values—ask explicitly if uncertain.
- Re-plan only if a blocker is discovered (missing parameter, failed tool, new mission context).

## Output & Communication Style
- Responses must be short, structured, and CLI-friendly.
- For planning: return strict JSON matching the required schema.
- For execution: emit clear status lines or structured events (thought, action, result, ask_user).
- For ask_user: provide exactly one direct, actionable question.

## Roles
- **Planner**: Convert the mission into a Todo List (JSON). Insert "ASK_USER" placeholders where input is required. Ensure dependencies are correct and non-circular.
- **Executor**: Process each Todo step in order. For each step: generate a thought, decide one next action, execute, record observation.
- **Clarifier**: When encountering ASK_USER, pause execution and request the answer in a single, well-phrased question. Resume once the answer is given.
- **Finisher**: Stop once all Todo items are resolved or the mission goal is clearly achieved. Emit a "complete" action with a final status message.

## Constraints
- Always produce valid JSON when asked.
- Do not output code fences, extra commentary, or natural-language paragraphs unless explicitly required.
- Keep rationales ≤2 sentences.
- Be strict: only valid action types are {tool_call, ask_user, complete, update_todolist, error_recovery}.
"""

# Ich brauche noch eine Messsage History Klasse die die Kommunikation zwischen dem Agent und dem User speichert
# Die sollte ungefähr so aussehen:
# messages=[
#  {"role": "system", "content": system_prompt},
#  {"role": "user", "content": user_prompt}
#  {"role": "assistant", "content": assistant_prompt}
#  {"role": "user", "content": user_prompt}
#  {"role": "assistant", "content": assistant_prompt}
#  {"role": "user", "content": user_prompt}
# ],
# Der System Prompt ist immer der erste Eintrag in der Liste. Ich will aber nicht, dass ich dem LLM den
# gesamten Chat History sende. Ich will nur den System Prompt und die letzten n messages (User und Assistant) senden.
# Das n sollte einstellbar sein!
class MessageHistory:
    MAX_MESSAGES = 50
    SUMMARY_THRESHOLD = 40
    
    def __init__(self, system_prompt: str):
        # Store system prompt as the first message entry
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.messages = [self.system_prompt]

    def add_message(self, message: str, role: str) -> None:
        """
        Adds a message to the message history.
        Note: Call compress_history_async() manually if needed for compression.

        Args:
            message: The message to add.
            role: The role of the message.
        """
        self.messages.append({"role": role, "content": message})
    
    async def compress_history_async(self) -> None:
        """Summarize alte Messages mit LLM."""
        import litellm
        
        old_messages = self.messages[1:self.SUMMARY_THRESHOLD]  # Skip system
        
        summary_prompt = f"""Summarize this conversation history concisely:

{json.dumps(old_messages, indent=2)}

Provide a 2-3 paragraph summary of key decisions, results, and context."""
        
        try:
            response = await litellm.acompletion(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0
            )
            
            summary = response.choices[0].message.content
            
            self.messages = [
                self.system_prompt,
                {"role": "system", "content": f"[Previous context summary]\n{summary}"},
                *self.messages[self.SUMMARY_THRESHOLD:]
            ]
        except Exception as e:
            # If compression fails, just keep the recent messages
            self.messages = [self.system_prompt] + self.messages[-self.SUMMARY_THRESHOLD:]

    def get_last_n_messages(self, n: int) -> List[Dict[str, Any]]:
        """
        Gets the last n message pairs (user and assistant) in chronological order,
        always including the system prompt as the first message. If there is an
        incomplete trailing message (no pair), it is ignored.

        Args:
            n: The number of message pairs to get.
        """
        if n <= 0:
            return [self.system_prompt]

        if n == -1:
            return self.messages

        # Exclude the system prompt from pairing logic
        body = self.messages[1:]
        num_pairs = len(body) // 2

        if num_pairs == 0:
            return [self.system_prompt]

        if n >= num_pairs:
            # Return all complete pairs
            return [self.system_prompt] + body[: num_pairs * 2]

        # Return only the last n pairs, preserving chronological order
        start_index = len(body) - (n * 2)
        return [self.system_prompt] + body[start_index:]

    def replace_system_prompt(self, system_prompt: str) -> None:
        """
        Replaces the system prompt with the new system prompt.

        Args:
            system_prompt: The new system prompt.
        """
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.messages[0] = self.system_prompt

    def __str__(self) -> str:
        return json.dumps(self.messages, ensure_ascii=False, indent=2)


class ActionType(Enum):
    TOOL = "tool_call"
    ASK  = "ask_user"
    DONE = "complete"
    REPLAN = "replan"

@dataclass
class Action:
    type: ActionType  # tool_call, ask_user, complete, replan
    
    # For tool_call:
    tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    
    # For ask_user:
    question: Optional[str] = None
    answer_key: Optional[str] = None  # Stable identifier
    
    # For complete:
    summary: Optional[str] = None

    @staticmethod
    def from_json(json_str: str) -> "Action":
        """
        Creates an Action object from a JSON string.
        """
        # Accept both JSON string and already-parsed dict
        if isinstance(json_str, (str, bytes, bytearray)):
            data = json.loads(json_str)
        elif isinstance(json_str, dict):
            data = json_str
        else:
            raise TypeError("Action.from_json expects str|bytes|bytearray|dict")

        action_type_value = data.get("type")
        action_type = action_type_value if isinstance(action_type_value, ActionType) else ActionType(action_type_value)

        return Action(
            type=action_type,
            tool=data.get("tool"),
            tool_input=data.get("tool_input") or data.get("input", {}),  # Support both names
            question=data.get("question"),
            answer_key=data.get("answer_key"),
            summary=data.get("summary") or data.get("message"))

@dataclass
class Thought:
    step_ref: int
    rationale: str  # Max 2 sentences
    action: Action  # Directly the executable Action
    expected_outcome: str
    confidence: float = 1.0  # 0-1, for later Uncertainty-Handling

    @staticmethod
    def from_json(json_str: str) -> "Thought":
        """
        Creates a Thought object from a JSON string.
        """
        # Accept both JSON string and already-parsed dict
        if isinstance(json_str, (str, bytes, bytearray)):
            data = json.loads(json_str)
        elif isinstance(json_str, dict):
            data = json_str
        else:
            raise TypeError("Thought.from_json expects str|bytes|bytearray|dict")
        return Thought(
            step_ref=data.get("step_ref") or data.get("next_step_ref"),  # Support both names
            rationale=data["rationale"],
            action=Action.from_json(data["action"]),
            expected_outcome=data["expected_outcome"],
            confidence=data.get("confidence", 1.0))


@dataclass
class AgentEventType(Enum):
    THOUGHT = "thought"
    ACTION = "action"
    TOOL_STARTED = "tool_started"
    TOOL_RESULT = "tool_result"
    ASK_USER = "ask_user"
    STATE_UPDATED = "state_updated"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class AgentEvent:
    type: AgentEventType
    data: Dict[str, Any]


@dataclass
class Observation:
    success: bool
    error: Optional[str] = None
    data: Dict[str, Any] = None
    requires_user: bool = False


def build_system_prompt(system_prompt: str, mission: str, todo_list: Optional[str] = "") -> str:
    """
    Build the system prompt from base, mission, and todo list sections.

    Args:
        system_prompt (str): The static base instructions (timeless context).
        mission (str): The agent's mission or current objective.
        todo_list (str, optional): Current todo list, may be empty. Defaults to "".

    Returns:
        str: Final system prompt ready for use.
    """
    prompt = f"""<Base>
{system_prompt.strip()}
</Base>

<Mission>
{mission.strip() if mission else ""}
</Mission>

<TODOList>
{todo_list.strip() if todo_list else ""}
</TODOList>"""
    return prompt



class Agent:
    def __init__(self, 
        name: str, 
        description: str, 
        system_prompt: Optional[str],
        mission: Optional[str],
        tools: List[Tool],
        todo_list_manager: TodoListManager,
        state_manager: StateManager,
        llm):
        """
        Initializes the Agent with the given name, description, system prompt, mission, tools, and planner.
        Args:
            name: The name of the agent.
            description: The description of the agent.
            system_prompt: The system prompt for the agent. This the generic part of the agent's system prompt.
            mission: The mission for the agent. This is a collection of tasks that the agent needs to complete.
            tools: The tools for the agent. This is a collection of tools that the agent can use to complete the tasks.
            planner: The planner for the agent. This is the planner that the agent uses to plan the tasks.
            state_manager: The state manager for the agent. This is the state manager that the agent uses to save the state of the agent.
        """

        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.mission = mission
        self.tools = tools
        self.tools_description = self._get_tools_description()
        self.tools_schema = self._get_tools_schema()
        self.todo_list_manager = todo_list_manager
        self.state_manager = state_manager
        self.state = None
        self.message_history = MessageHistory(build_system_prompt(system_prompt, mission, self.tools_description))
        self.logger = structlog.get_logger().bind(agent=name)


    async def execute(self, user_message: str, session_id: str) -> AsyncIterator[AgentEvent]:
        """
        Executes the agent with the given user message using ReAct architecture:
        1) Load state
        2) Set mission (only on first call)
        3) Answer pending question (if any)
        4) Create plan (if not exists)
        5) Run ReAct loop

        Args:
            user_message: The user message to execute the agent.
            session_id: The session id to execute the agent.

        Returns:
            An async iterator of AgentEvent.
        """
        # 1. State laden
        self.state = await self.state_manager.load_state(session_id)
        self.logger.info("execute_start", session_id=session_id)

        # 2. Mission setzen (nur beim ersten Call)
        if self.mission is None:
            self.mission = user_message
            self.logger.info("mission_set", session_id=session_id, mission_preview=self.mission[:100])

        # 3. Pending Question beantworten (falls vorhanden)
        if self.state.get("pending_question"):
            answer_key = self.state["pending_question"]["answer_key"]
            self.state.setdefault("answers", {})[answer_key] = user_message
            self.state.pop("pending_question")
            await self.state_manager.save_state(session_id, self.state)
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, 
                            data={"answer_received": answer_key})
            self.logger.info("answer_received", session_id=session_id, answer_key=answer_key)
        
        # 4. Plan erstellen (falls noch nicht vorhanden)
        todolist_existed = self.state.get("todolist_id") is not None
        todolist = await self._get_or_create_plan(session_id)

        # Emit todolist created event if it was just created
        if not todolist_existed:
            yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                           data={"todolist_created": True,
                                 "todolist": todolist.to_markdown(),
                                 "items": len(todolist.items)})

        # 5. ReAct Loop
        async for event in self._react_loop(session_id, todolist):
            yield event



    async def _get_or_create_plan(self, session_id: str) -> TodoList:
        """
        Gets or creates the plan for this session.
        
        Args:
            session_id: The session id for the agent.
        
        Returns:
            A TodoList for the mission.
        """
        todolist_id = self.state.get("todolist_id")
        
        if todolist_id:
            # Load existing plan
            try:
                todolist = await self.todo_list_manager.load_todolist(todolist_id)
                self.logger.info("plan_loaded", session_id=session_id, todolist_id=todolist_id)
                return todolist
            except FileNotFoundError:
                self.logger.warning("plan_not_found", session_id=session_id, todolist_id=todolist_id)
                # Fall through to create new plan
        
        # Create new plan
        answers = self.state.get("answers", {})
        todolist = await self.todo_list_manager.create_todolist(
                mission=self.mission,
                tools_desc=self.tools_description,
                answers=answers
        )

        self.state["todolist_id"] = todolist.todolist_id
        await self.state_manager.save_state(session_id, self.state)
        self.logger.info("plan_created", session_id=session_id,
                        todolist_id=todolist.todolist_id, items=len(todolist.items))

        return todolist


    async def _react_loop(self, session_id: str, todolist: TodoList) -> AsyncIterator[AgentEvent]:
        """
        Echte ReAct-Schleife: Thought → Action → Observation → Repeat
        
        Args:
            session_id: The session id for the agent.
            todolist: The TodoList to execute.
            
        Yields:
            AgentEvent: Events during execution.
        """
        max_iterations = 50  # Safety limit
        iteration = 0
        
        while not self._is_plan_complete(todolist) and iteration < max_iterations:
            iteration += 1
            
            # 1. Nächster Step (PENDING oder FAILED mit Retries übrig)
            current_step = self._get_next_actionable_step(todolist)
            
            if not current_step:
                self.logger.info("no_actionable_steps", session_id=session_id)
                break
            
            self.logger.info("step_start", session_id=session_id, step=current_step.position, 
                            desc=current_step.description[:50])
            
            # 2. THOUGHT: Analysiere + entscheide Tool
            context = self._build_thought_context(current_step, todolist)
            thought = await self._generate_thought_with_context(context)
            
            yield AgentEvent(type=AgentEventType.THOUGHT, 
                            data={"step": current_step.position, "thought": asdict(thought)})
            
            # 3. ACTION: Führe aus
            if thought.action.type == ActionType.ASK:
                # User-Input benötigt
                answer_key = thought.action.answer_key or f"step_{current_step.position}_q{current_step.attempts}"
                self.state["pending_question"] = {
                    "answer_key": answer_key,
                    "question": thought.action.question,
                    "for_step": current_step.position
                }
                await self.state_manager.save_state(session_id, self.state)
                
                yield AgentEvent(type=AgentEventType.ASK_USER, 
                                data={"question": thought.action.question})
                return  # Pause execution
            
            elif thought.action.type == ActionType.TOOL:
                # Tool ausführen
                observation = await self._execute_tool_safe(thought.action)
                
                # Runtime-Felder füllen
                current_step.chosen_tool = thought.action.tool
                current_step.tool_input = thought.action.tool_input
                current_step.execution_result = observation
                current_step.attempts += 1
                
                # Status updaten
                if observation.get("success"):
                    # Acceptance Criteria prüfen
                    if await self._check_acceptance(current_step, observation):
                        current_step.status = TaskStatus.COMPLETED
                        self.logger.info("step_completed", session_id=session_id,
                                       step=current_step.position)
                        # Emit step completed event
                        yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                       data={"step_completed": current_step.position,
                                             "description": current_step.description,
                                             "status": current_step.status.value})
                    else:
                        current_step.status = TaskStatus.FAILED
                        self.logger.warning("acceptance_failed", session_id=session_id,
                                          step=current_step.position)
                        yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                       data={"step_failed": current_step.position,
                                             "reason": "acceptance_criteria_not_met"})
                else:
                    current_step.status = TaskStatus.FAILED
                    self.logger.warning("step_failed", session_id=session_id,
                                      step=current_step.position,
                                      error=observation.get("error"))
                    yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                   data={"step_failed": current_step.position,
                                         "error": observation.get("error")})

                yield AgentEvent(type=AgentEventType.TOOL_RESULT, data=observation)
            
            elif thought.action.type == ActionType.REPLAN:
                # Plan anpassen
                todolist = await self._replan(current_step, thought, todolist)
                yield AgentEvent(type=AgentEventType.STATE_UPDATED, 
                                data={"plan_updated": True})
            
            elif thought.action.type == ActionType.DONE:
                # Frühzeitiger Abschluss mit finaler Antwort
                self.logger.info("early_completion", session_id=session_id,
                               step=current_step.position)
                current_step.status = TaskStatus.COMPLETED

                # Emit final answer before breaking
                final_answer = thought.action.summary if hasattr(thought.action, 'summary') else "Task completed"
                yield AgentEvent(type=AgentEventType.COMPLETE,
                                data={"message": final_answer, "summary": final_answer})
                break
            
            # 4. State + Plan persistieren
            await self.state_manager.save_state(session_id, self.state)
            await self.todo_list_manager.update_todolist(todolist)
            
            # 5. Error Recovery (falls Step failed)
            if current_step.status == TaskStatus.FAILED:
                if current_step.attempts < current_step.max_attempts:
                    # Retry mit angepasstem Context
                    current_step.status = TaskStatus.PENDING
                    self.logger.info("retry_step", session_id=session_id, 
                                    step=current_step.position, 
                                    attempt=current_step.attempts)
        else:
                    # Abbrechen oder Replan triggern
                    self.logger.error("step_exhausted", session_id=session_id, 
                                    step=current_step.position)
                    # Optional: ask_user für manuelle Intervention
        
        # Fertig
        yield AgentEvent(type=AgentEventType.COMPLETE, 
                        data={"todolist": todolist.to_markdown()})


    def _get_next_actionable_step(self, todolist: TodoList) -> Optional[TodoItem]:
        """Findet nächsten Step, der ausgeführt werden kann."""
        for step in sorted(todolist.items, key=lambda s: s.position):
            if step.status == TaskStatus.COMPLETED:
                continue
            
            if step.status == TaskStatus.PENDING:
                # Dependencies erfüllt?
                deps_met = all(
                    any(s.position == dep and s.status == TaskStatus.COMPLETED 
                        for s in todolist.items)
                    for dep in step.dependencies
                )
                if deps_met:
                    return step
            
            if step.status == TaskStatus.FAILED and step.attempts < step.max_attempts:
                return step  # Retry
        
        return None


    def _build_thought_context(self, step: TodoItem, todolist: TodoList) -> Dict[str, Any]:
        """Baut Context für Thought-Generation."""
        # Ergebnisse vorheriger Steps (inkl. Fehler für Retry-Kontext)
        previous_results = [
            {
                "step": s.position,
                "description": s.description,
                "tool": s.chosen_tool,
                "result": s.execution_result,
                "status": s.status.value
            }
            for s in todolist.items 
            if s.execution_result and s.position < step.position
        ]
        
        # Extrahiere Fehler vom aktuellen Step (für Retry)
        current_error = None
        if step.execution_result and not step.execution_result.get("success"):
            current_error = {
                "error": step.execution_result.get("error"),
                "type": step.execution_result.get("type"),
                "hints": step.execution_result.get("hints", []),
                "attempt": step.attempts,
                "max_attempts": step.max_attempts
            }
        
        # Sammle verfügbare Context-Daten von vorherigen Python Steps
        available_context = {}
        for s in todolist.items:
            if (s.status == TaskStatus.COMPLETED and 
                s.chosen_tool == "python" and 
                s.execution_result and 
                s.execution_result.get("context_updated")):
                # Merge context from previous steps
                ctx = s.execution_result.get("context_updated", {})
                if isinstance(ctx, dict):
                    available_context.update(ctx)
        
        return {
            "current_step": step,
            "current_error": current_error,
            "previous_results": previous_results[-5:],  # Last 5
            "available_context": available_context,  # NEW: Context from previous Python steps
            "available_tools": self.tools_description,
            "user_answers": self.state.get("answers", {}),
            "mission": self.mission,
        }


    async def _generate_thought_with_context(self, context: Dict[str, Any]) -> Thought:
        """
        ReAct Thought Generation with provided context.

        Args:
            context: Context dict with current_step, previous_results, etc.

        Returns:
            A Thought for the next step.
        """
        current_step = context["current_step"]
        
        schema_hint = {
            "step_ref": "int",
            "rationale": "string (<= 2 sentences)",
            "action": {
                "type": "tool_call|ask_user|complete|replan",
                "tool": "string|null (for tool_call)",
                "tool_input": "object (for tool_call)",
                "question": "string (for ask_user)",
                "answer_key": "string (for ask_user)",
                "summary": "string (for complete)"
            },
            "expected_outcome": "string",
            "confidence": "float (0-1, optional)"
        }

        # Get the last 4 message pairs from history
        messages = self.message_history.get_last_n_messages(4)

        # Build error context if this is a retry
        error_context = ""
        if context.get("current_error"):
            error = context["current_error"]
            error_context = f"""
PREVIOUS ATTEMPT FAILED (Attempt {error['attempt']}/{error['max_attempts']}):
Error Type: {error.get('type', 'Unknown')}
Error Message: {error.get('error', 'Unknown error')}
"""
            if error.get('hints'):
                error_context += f"\nHints to fix:\n"
                for hint in error['hints']:
                    error_context += f"  - {hint}\n"
            error_context += "\nPlease analyze the error and provide a corrected solution.\n"

        # Build context note for Python tool
        context_note = ""
        available_ctx = context.get("available_context", {})
        if available_ctx:
            context_note = f"""
AVAILABLE CONTEXT FROM PREVIOUS STEPS:
{json.dumps(available_ctx, ensure_ascii=False, indent=2)}

IMPORTANT: If you need data from previous Python steps, either:
1. Pass the context via 'context' parameter (recommended for simple data)
2. Re-read the data from the source file (CSV, JSON, etc.)

NOTE: Each Python tool call has an ISOLATED namespace. Variables from previous steps do NOT persist!
"""

        messages.append({"role": "user", "content": (
            "You are the ReAct Execution Agent.\n"
            "Analyze the current step and choose the best action.\n\n"
            f"CURRENT_STEP:\n{json.dumps(asdict(current_step), ensure_ascii=False, indent=2)}\n\n"
            f"{error_context}"
            f"{context_note}"
            f"MISSION:\n{context.get('mission', '')}\n\n"
            f"PREVIOUS_RESULTS:\n{json.dumps(context.get('previous_results', []), ensure_ascii=False, indent=2)}\n\n"
            f"USER_ANSWERS:\n{json.dumps(context.get('user_answers', {}), ensure_ascii=False, indent=2)}\n\n"
            f"AVAILABLE_TOOLS:\n{context.get('available_tools', '')}\n\n"
            "Rules:\n"
            "- Choose the appropriate tool to fulfill the step's acceptance criteria.\n"
            "- If this is a retry after an error, FIX the previous error using the hints provided.\n"
            "- For Python code errors: Read the error message and hints carefully, then correct the code.\n"
            "- **CRITICAL**: Each Python tool call is ISOLATED - variables don't persist between calls!\n"
            "  → Always re-read data or pass via context parameter.\n"
            "  → Don't assume 'df' or other variables from previous steps exist.\n"
            "- If information is missing, use ask_user action.\n"
            "- If the step is already fulfilled, use complete action.\n"
            "- If the plan needs adjustment, use replan action.\n"
            "Return STRICT JSON only (no extra text) matching this schema:\n"
            f"{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        )})

        self.logger.info("llm_call_thought_start", step=current_step.position)
        response = await litellm.acompletion(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw_content = response.choices[0].message.content
        self.message_history.add_message(raw_content, "assistant")

        self.logger.info("llm_call_thought_end", step=current_step.position)
        
        try:
            return Thought.from_json(raw_content)
        except Exception as e:
            self.logger.error("thought_parse_failed", step=current_step.position, error=str(e))
            raise


    async def _check_acceptance(self, step: TodoItem, observation: Dict) -> bool:
        """Prüft ob Acceptance Criteria erfüllt sind."""
        # Einfache Heuristik: Wenn Tool erfolgreich war, ist Step erfüllt
        # TODO: Später mit LLM-Call verfeinern für komplexere Criteria
        return observation.get("success", False)


    def _is_plan_complete(self, todolist: TodoList) -> bool:
        """Check ob alle Steps completed/skipped sind."""
        return all(
            s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) 
            for s in todolist.items
        )


    async def _execute_tool_safe(self, action: Action) -> Dict[str, Any]:
        """
        Executes a tool with the given action safely.
        
        Args:
            action: The action containing tool and tool_input.
        
        Returns:
            Observation dict with success flag and data/error.
        """
        tool = self._get_tool(action.tool)
        if not tool:
            return {"success": False, "error": f"Tool '{action.tool}' not found"}
        
        # Use execute_safe if available, otherwise execute
        if hasattr(tool, "execute_safe"):
            return await tool.execute_safe(**(action.tool_input or {}))
        else:
            try:
                result = await tool.execute(**(action.tool_input or {}))
                return result
            except Exception as e:
                import traceback
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }


    async def _replan(self, current_step: TodoItem, thought: Thought, todolist: TodoList) -> TodoList:
        """
        Adjusts the plan based on current situation.
        
        Args:
            current_step: The step that triggered replanning.
            thought: The thought that suggested replanning.
            todolist: The current todolist.
        
        Returns:
            Updated TodoList.
        """
        # TODO: Implement intelligent replanning
        # For now, just mark the step as skipped and continue
        self.logger.warning("replan_requested", step=current_step.position, 
                          rationale=thought.rationale)
        current_step.status = TaskStatus.SKIPPED
        return todolist


    def _get_tools_description(self) -> str:
        """
        Gets the description of the tools available.
        """
        lines = []
        for tool in self.tools:
            try:
                schema_json = json.dumps(tool.parameters_schema, ensure_ascii=False, indent=2)
            except Exception:
                schema_json = "{}"
            lines.append(
                f"- {tool.name}: {tool.description}\n"
                f"  parameters_schema:\n{schema_json}"
            )
        return "\n".join(lines)


    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Gets the schema of the tools available which can be used as a function calling schema for the LLM.
        """
        return [tool.function_tool_schema for tool in self.tools]


    async def _decide_next_action(self, thought: Thought, next_step: TodoItem) -> Action:
        """
        Decides the next action for the next step based on the thought.
        Since Thought.action is now directly an Action, we just return it.
        """
        return thought.action


    async def _execute_action(self, action: Action) -> Dict[str, Any]:
        """
        Executes the action for the next step.
        """
        if action.type == ActionType.TOOL:            
            tool = self._get_tool(action.tool)
            if not tool:
                return {"success": False, "error": f"Tool '{action.tool}' not found"}
            self.logger.info("tool_execute_start", tool=action.tool)
            return await tool.execute(**(action.tool_input or {}))
            
        elif action.type == ActionType.ASK:
            question_text = action.question or "I need additional information to proceed."
            return {"success": False, "requires_user": True, "question": question_text}
        
        elif action.type == ActionType.DONE:
            return {"success": True, "done": True, "summary": action.summary}
        
        elif action.type == ActionType.REPLAN:
            return {"success": True, "replan": True}
        
        else:
            raise ValueError(f"Invalid action type: {action.type}")


    def _get_tool(self, tool_name: str) -> Tool:
        """
        Gets the tool from the tools list where the name matches the tool_name
        """

        # check if tool_name starts with functions.
        if tool_name.startswith("functions."):
            tool_name = tool_name[len("functions."):]

        return next((tool for tool in self.tools if tool.name == tool_name), None)


    # create a static method to create an agent
    @staticmethod
    def create_agent(name: str, description: str, system_prompt: str, mission: str, work_dir: str, llm) -> "Agent":
        """
        Creates an agent with the given name, description, system prompt, mission, and work directory.
        The agent will be created with the following tools:
        - WebSearchTool
        - WebFetchTool
        - PythonTool
        - GitHubTool
        - GitTool
        - FileReadTool
        - FileWriteTool
        - PowerShellTool
        The agent will be created with the following planner:
        - TodoListManager
        The agent will be created with the following state manager:
        - StateManager

        Args:
            name: The name of the agent.
            description: The description of the agent.
            system_prompt: The system prompt for the agent.
            mission: The mission for the agent.
            work_dir: The work directory for the agent.
            llm: The llm for the agent.

        Returns:
            An agent with the given name, description, system prompt, mission, and work directory.
        """
        tools = [
            WebSearchTool(),
            WebFetchTool(),
            PythonTool(),
            GitHubTool(),
            GitTool(),
            FileReadTool(),
            FileWriteTool(),
            PowerShellTool(),
        ]

        system_prompt = GENERIC_SYSTEM_PROMPT if system_prompt is None else system_prompt
        work_dir = Path(work_dir)
        work_dir.mkdir(exist_ok=True)

        # todolist directory is work_dir/todolists
        todolist_dir = work_dir / "todolists"
        todolist_dir.mkdir(exist_ok=True)
        planner = TodoListManager(base_dir=todolist_dir)

        # state directory is work_dir/states
        state_dir = work_dir / "states"
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(state_dir=state_dir)

        return Agent(name, description, system_prompt, mission, tools, planner, state_manager, llm)

    @staticmethod
    def create_rag_agent(
        session_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        work_dir: Optional[str] = None,
        llm = None
    ) -> "Agent":
        """
        Create an agent with RAG capabilities for document search and retrieval.

        Args:
            session_id: Unique session identifier
            user_context: User context for security filtering (user_id, org_id, scope)
            work_dir: Working directory for state and todolists (default: ./rag_agent_work)
            llm: LLM instance to use (default: uses litellm default)

        Returns:
            Agent instance with RAG tools and system prompt

        Example:
            >>> agent = Agent.create_rag_agent(
            ...     session_id="rag_session_001",
            ...     user_context={"user_id": "user123", "org_id": "org456", "scope": "shared"}
            ... )
            >>> async for event in agent.execute("What does the manual say about pumps?", session_id):
            ...     print(event)
        """
        from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
        from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT

        # Create RAG tools with user context
        rag_tools = [
            SemanticSearchTool(user_context=user_context)
        ]

        # Set default work directory
        if work_dir is None:
            work_dir = "./rag_agent_work"

        work_dir_path = Path(work_dir)
        work_dir_path.mkdir(exist_ok=True)

        # Create todolist manager
        todolist_dir = work_dir_path / "todolists"
        todolist_dir.mkdir(exist_ok=True)
        planner = TodoListManager(base_dir=todolist_dir)

        # Create state manager
        state_dir = work_dir_path / "states"
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(state_dir=state_dir)

        # Use default LLM if not provided
        if llm is None:
            llm = litellm

        # Create agent with RAG prompt and tools
        return Agent(
            name="RAG Knowledge Assistant",
            description="Agent with semantic search capabilities for enterprise documents",
            system_prompt=RAG_SYSTEM_PROMPT,
            mission=None,  # Mission will be set per execute() call
            tools=rag_tools,
            todo_list_manager=planner,
            state_manager=state_manager,
            llm=llm
        )


# ============================================
# MAIN ENTRY POINT FOR QUICK DEBUGGING
# ============================================
def main():
    """Minimal entrypoint to construct the Agent and run until thought generation."""
    import os
    import asyncio
    import uuid
    from pathlib import Path

    # Ensure API key for LLM is available
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Please set OPENAI_API_KEY environment variable before running.")
        return

    name = "AgentV2-Debug"
    description = "Lightweight debug run to reach thought generation."
    system_prompt = GENERIC_SYSTEM_PROMPT

    # Mission: Ask the user for the directory name and the content of the README.txt file, then create the directory and add the README.txt file with the provided content.
    # mission = (        
    #     "Create the directory with the specified name and add a README.txt file inside it containing the provided content."
    #     "Ask the user for the name of the directory to create and the content to put inside a README.txt file. "
    # )
    mission = r"""
# MISSION — CSV nach Markdown (einfach)

## ZIEL
- Lies die CSV-Datei `assignments/assignment3/data/heart.csv` ein und erzeuge daraus eine Markdown-Tabelle.
- Speichere das Ergebnis unter `capstone/documents/report.md`.

## AUFGABEN
1. CSV mit der Python-Standardbibliothek `csv` einlesen (optional: Delimiter per Sniffer erkennen).
2. Erste Zeile als Header verwenden; falls kein Header vorhanden ist, Spaltennamen `col_1..N` generieren.
3. Alle Zeilen als einfache Markdown-Tabelle ausgeben (Header + Trennzeile + Datenzeilen).
4. Markdown-Datei nach `capstone/documents/report.md` schreiben.

## REGELN
- Nur vorhandene Tools verwenden: `python`, `file_read`, `file_write`.
- Keine externen Bibliotheken (kein pandas).
- Kurze, deterministische Ausführung ohne zusätzliche Analysen/Statistiken.

## ERFOLGSKRITERIEN
- `capstone/documents/report.md` existiert und enthält eine Markdown-Tabelle mit Header und mindestens einer Datenzeile.
"""

    # Use a local work directory next to this file
    work_dir = str((Path(__file__).parent / ".debug_work").resolve())

    # Create agent
    agent = Agent.create_agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        mission=mission,
        work_dir=work_dir,
        llm=None,
    )

    # Minimal inputs for execute()
    session_id = f"debug-{uuid.uuid4()}"
    #user_message = "Create a new directory and add a README.txt file inside it containing a hello_world code example."
    user_message = "Führe die Mission aus"

    print(f"Starting Agent execute() with session_id={session_id}")
    try:
        async def drive():
            current_input = user_message
            done = False
            while True:
                async for ev in agent.execute(user_message=current_input, session_id=session_id):
                    if ev.type.name == AgentEventType.ASK_USER.name:
                        print("QUESTION:", ev.data.get("question"))
                        current_input = input("> ").strip()
                    elif ev.type.name == AgentEventType.STATE_UPDATED.name:
                        print("STATE UPDATED:", ev.data)
                    elif ev.type.name == AgentEventType.COMPLETE.name:
                        print("COMPLETED:")
                        print(ev.data.get("todolist"))
                        done = True
                        # Do NOT break here; let the async generator finish naturally
                        # to avoid cancellation at the yield suspension point.
                if done:
                    # Completed; exit outer loop after the async generator finishes
                    break

        asyncio.run(drive())
        print("Agent session finished.")
    except Exception as exc:
        print(f"Agent execution failed: {exc}")


if __name__ == "__main__":
    main()