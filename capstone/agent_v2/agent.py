# An Agent class

from dataclasses import field
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, AsyncIterator, Dict, List, Optional
import uuid
from attr import asdict, dataclass
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
    def __init__(self, system_prompt: str):
        # Store system prompt as the first message entry
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.messages = [self.system_prompt]

    def add_message(self, message: str, role: str) -> None:
        """
        Adds a message to the message history.

        Args:
            message: The message to add.
            role: The role of the message.
        """
        self.messages.append({"role": role, "content": message})

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
    PLAN = "update_todolist"
    ERR  = "error_recovery"

@dataclass
class ThoughtAction:
    type: ActionType
    tool: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    question: Optional[str] = None   # nur bei ask_user
    message: Optional[str] = None    # nur bei complete

    @staticmethod
    def from_json(json_str: str) -> "ThoughtAction":
        """
        Creates a ThoughtAction object from a JSON string.
        """
        # Accept both JSON string and already-parsed dict
        if isinstance(json_str, (str, bytes, bytearray)):
            data = json.loads(json_str)
        elif isinstance(json_str, dict):
            data = json_str
        else:
            raise TypeError("ThoughtAction.from_json expects str|bytes|bytearray|dict")

        action_type_value = data.get("type")
        action_type = action_type_value if isinstance(action_type_value, ActionType) else ActionType(action_type_value)

        return ThoughtAction(
            type=action_type,
            tool=data.get("tool"),
            input=data.get("input", {}),
            question=data.get("question"),
            message=data.get("message"))

@dataclass
class Thought:
    next_step_ref: int
    rationale: str                   # kurz, max. 2 Sätze
    action: ThoughtAction
    expected_outcome: str

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
            next_step_ref=data["next_step_ref"],
            rationale=data["rationale"],
            action=ThoughtAction.from_json(data["action"]),
            expected_outcome=data["expected_outcome"])

# create an Action class which is a dataclass with the following fields:
# - type: ActionType
# - tool: Optional[str]
# - input: Dict[str, Any]
# - question: Optional[str]
# - message: Optional[str]
@dataclass
class Action:
    type: ActionType
    tool: Optional[str]
    input: Dict[str, Any]
    question: Optional[str] = None
    message: Optional[str] = None

    @staticmethod
    def from_json(json_str: str) -> "Action":
        """
        Creates an Action object from a JSON string.
        """
        data = json.loads(json_str)
        return Action(
            type=ActionType(data["type"]),
            tool=data["tool"],
            input=data["input"],
            question=data.get("question"),
            message=data.get("message"))


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
        Executes the agent with the given user message using a Pre-Clarification pass:
        1) Collect & resolve all missing required info (closed-form questions).
        2) Create a final TodoList (no ASK_USER, no open_questions).
        3) Run the ReAct loop to complete the tasks.

        Args:
            user_message: The user message to execute the agent.
            session_id: The session id to execute the agent.

        Returns:
            An async iterator of AgentEvent.
        """
        # --- 0) Load state -------------------------------------------------------
        self.logger.info("execute_start", session_id=session_id, has_mission=bool(self.mission))
        self.state = await self.state_manager.load_state(session_id)

        if self.mission is None:
            self.mission = user_message
            self.logger.info("mission_set_from_user", session_id=session_id, mission_preview=self.mission[:120])

        # If we were awaiting an answer, consume it immediately
        if self.state.get("pending_question"):
            answer = user_message.strip()
            pending_question = self.state.pop("pending_question")
            # store the answer by stable key
            answers = self.state.setdefault("answers", {})
            answers[pending_question["answer_key"]] = answer
            await self.state_manager.save_state(session_id, self.state)
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, data={"answers": answers})
            self.logger.info("answer_captured", session_id=session_id, answer_key=pending_question["answer_key"])

            # Nach einer beantworteten Frage: user_message nicht als neues inhaltliches Prompt verwenden
            # (wir bleiben im Clarification-Flow). Kein return hier: wir laufen weiter und prüfen,
            # ob noch weitere Fragen offen sind / ob wir planen können.

        # --- 1) Update message history & mission --------------------------------
        self.message_history.add_message(user_message, "user")
        self.state["message_history"] = self.message_history.messages
        self.state["last_user_message"] = user_message
        self.state["mission"] = self.mission
        answers = self.state.setdefault("answers", {})
        await self.state_manager.save_state(session_id, self.state)
        self.logger.info("state_saved_post_user", session_id=session_id)

        # --- 2) Pre-Clarification Gate (nur wenn noch kein finaler Plan existiert) ---
        todolist = None
        if not self.state.get("todolist_id"):
            # 2.a) Fragen extrahieren, falls noch nicht geschehen
            if "clar_questions" not in self.state:
                clar_qs = await self.todo_list_manager.extract_clarification_questions(
                    mission=self.mission,
                    tools_desc=self.tools_description
                )
                self.state["clar_questions"] = clar_qs or []
                await self.state_manager.save_state(session_id, self.state)
                self.logger.info("clar_questions_extracted", session_id=session_id, count=len(self.state["clar_questions"]))

            # 2.b) Unbeantwortete Frage suchen (per stable key)
            unanswered = next(
                (q for q in self.state["clar_questions"] if q.get("key") not in answers),
                None
            )
            if unanswered:
                # ask user now; pause execution until answered
                self.state["pending_question"] = {
                    "answer_key": unanswered["key"],
                    "question": unanswered["question"]
                }
                await self.state_manager.save_state(session_id, self.state)
                yield AgentEvent(type=AgentEventType.ASK_USER, data={"question": unanswered["question"]})
                self.logger.info("ask_user", session_id=session_id, question_key=unanswered["key"])
                return

            # 2.c) Alle Fragen beantwortet -> finalen Plan erstellen (No-ASK mode)
            todolist = await self.todo_list_manager.create_todolist(
                mission=self.mission,
                tools_desc=self.tools_description,
                answers=answers
            )
            self.logger.info("todolist_created", session_id=session_id, items=len(todolist.items))
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, data={"todolist": todolist.to_markdown()})

            # 2.d) Harte Guards: keine open_questions, keine ASK_USER-Platzhalter
            if getattr(todolist, "open_questions", None):
                raise ValueError("Final plan contains open_questions, expected none in No-ASK mode.")

            for item in todolist.items:
                if getattr(item, "parameters", None):
                    for v in item.parameters.values():
                        if isinstance(v, str) and v.strip().upper() == "ASK_USER":
                            raise ValueError("Final plan contains ASK_USER placeholder, expected none.")

            # 2.e) Plan persistieren
            self.state["todolist_id"] = todolist.todolist_id
            await self.state_manager.save_state(session_id, self.state)
            await self.todo_list_manager.update_todolist(todolist)  # persist current version if needed
            self.logger.info("todolist_persisted", session_id=session_id, todolist_id=todolist.todolist_id)

        else:
            # Es existiert bereits ein Plan (Resume-Fall)
            # Lade ihn (oder nutze deinen bisherigen Helper)
            if hasattr(self.todo_list_manager, "load_todolist_by_id"):
                todolist = await self.todo_list_manager.load_todolist_by_id(self.state["todolist_id"])
            else:
                todolist = await self._create_or_get_todolist(session_id, self.state)            

        # --- 3) ReAct Loop über die finale TodoList ------------------------------
        for next_step in todolist.items:
            # Hydratation: Parameter ggf. aus answers einsetzen
            # self._hydrate_parameters_from_answers(next_step)
            # self.logger.info("step_begin", session_id=session_id, position=next_step.position, tool=next_step.tool)

            # 1) Thought
            thought = await self._generate_thought(next_step)
            yield AgentEvent(type=AgentEventType.THOUGHT, data={"for_step": next_step.position, "thought": asdict(thought)})
            self.logger.info("thought_generated", session_id=session_id, position=next_step.position, action_type=thought.action.type.value)

            # 2) Action
            action = await self._decide_next_action(thought, next_step)
            yield AgentEvent(type=AgentEventType.ACTION, data={"for_step": next_step.position, "action": action.type.value})
            self.logger.info("action_decided", session_id=session_id, position=next_step.position, action=action.type.value, tool=action.tool)

            # 3) Execute
            observation = await self._execute_action(action)
            self.logger.info("action_executed", session_id=session_id, position=next_step.position, success=bool(observation.get("success")))

            # 3a) If the action requires user input, pause and ask
            if observation.get("requires_user"):
                question_text = observation.get("question") or "I need additional information to proceed."
                # Store a pending question with a stable key tied to this step
                self.state["pending_question"] = {
                    "answer_key": f"step_{next_step.position}_answer",
                    "question": question_text,
                }
                await self.state_manager.save_state(session_id, self.state)
                yield AgentEvent(type=AgentEventType.ASK_USER, data={"question": question_text})
                self.logger.info("ask_user", session_id=session_id, question_key=f"step_{next_step.position}_answer")
                return

            # 4) State aktualisieren
            self.state["last_observation"] = observation
            next_step.status = TaskStatus.COMPLETED if observation.get("success") else TaskStatus.FAILED

            # 5) Persist
            await self.state_manager.save_state(session_id, self.state)
            await self.todo_list_manager.update_todolist(todolist)
            self.logger.info("state_and_plan_updated", session_id=session_id, position=next_step.position)

            # Optional: Early stop bei Fehler + Re-Plan-Hook
            # if not observation.get("success") and self.allow_replan_on_failure:
            #     break / trigger replan...

        # --- 4) Abschluss ---------------------------------------------------------
        yield AgentEvent(type=AgentEventType.COMPLETE, data={"todolist": todolist.to_markdown()})
        self.logger.info("execute_complete", session_id=session_id)
        return



    async def _create_or_get_todolist(self, session_id: str, state: Dict[str, Any]) -> Optional[TodoList]:
        """
        Creates a new todolist for the mission if no todolist exists yet or loads the existing todolist

        Args:
            session_id: The session id for the agent.
            state: The state of the agent.

        Returns:
            A todolist for the mission.
        """
        todolist_id = state.get("todolist_id")
        # check if a plan has already been created for the mission
        if self.mission is None:
            mission = state.get("last_user_message")

        # check if the todolist is already created
        if not todolist_id:
            todolist = await self.todo_list_manager.create_todolist(mission, self.tools_description)
            state["todolist_id"] = todolist.todolist_id
            await self.state_manager.save_state(session_id, state)

            # update the message history with the new todolist
            system_prompt = build_system_prompt(system_prompt=self.system_prompt, mission=self.mission, todo_list=todolist.to_json())
            self.message_history.replace_system_prompt(system_prompt)

            # add a new message to the message history
            self.message_history.add_message(f"New todolist created: {todolist.to_json()}", "assistant")

            print(f"New todolist created:\n\n{todolist.to_markdown()}")

            return todolist
        else:
            todolist = await self.todo_list_manager.load_todolist(todolist_id)                
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


    def _hydrate_parameters_from_answers(self, step: TodoItem) -> None:
        """
        Hydrates the parameters of the step from the answers in the state.

        Args:
            step: The step to hydrate the parameters from the answers.
        """
        answers = self.state.get("answers", {})
        for k, v in list(step.parameters.items()):
            if isinstance(v, str) and v == "ASK_USER":
                if k in answers:
                    step.parameters[k] = answers[k]


    async def _generate_thought(self, next_step: TodoItem) -> Thought:
        """
        ReAct Thought Generation:
        Generates a thought for the next step. A thought is a plan for the next step.
        Therfore the following context is needed:
        - The next step
        - The tools available
        - The history of the agent
        - The system prompt of the agent
        - The mission of the agent
        - The todo list of the agent

        Args:
            next_step: The next step to generate a thought for.

        Returns:
            A thought for the next step. A thought is a plan for the next step which is a JSON object.
        """
        schema_hint = {
            "next_step_ref": "int",
            "rationale": "string (<= 2 sentences)",
            "action": {
                "type": "tool_call|ask_user|complete|update_todolist|error_recovery",
                "tool": "string|null",
                "input": "object",
                "question": "string? (ask_user)",
                "message": "string? (complete)"
            },
            "expected_outcome": "string"
        }

        # get the last 2 messages from the message history. this shall be sufficient for the LLM to plan the next action.
        messages = self.message_history.get_last_n_messages(4)

        # Provide recent state/observation context to enable correct parameterization (e.g., GitHub repo URL)
        state_context = {
            "answers": self.state.get("answers", {}),
            "last_observation": self.state.get("last_observation", {}),
        }

        messages.append({"role": "user", "content": (
            "You are the Planning & Action Selector.\n"
            "Pick exactly one next action for the next_step below.\n"
            f"NEXT_STEP:\n{next_step.to_json()}\n\n"
            f"AVAILABLE_CONTEXT (use to fill concrete tool parameters):\n{json.dumps(state_context, ensure_ascii=False)}\n\n"
            "Rules:\n"
            "- Prefer tools; ask_user only if info is missing.\n"
            "- ALWAYS include repo_path pointing to the project directory for ALL git operations.\n"
            "- When setting the remote, derive the URL strictly from github.create_repo -> repo_full_name: https://github.com/{owner}/{repo}.git.\n"
            "  Never guess <owner>; if repo_full_name is unavailable, ask_user for the GitHub owner/org.\n"
            "- If git remote add fails because origin exists, retry with action=set_url (same repo_path).\n"
            "- After configuring the remote, verify with git remote -v (operation=remote, action=list, with repo_path).\n"
            "- Push with upstream set: git push -u origin main (with repo_path).\n"
            "Return STRICT JSON only (no extra text). Return EXACTLY ONE JSON object (no arrays, no multiple objects) matching this schema:\n"
            f"{json.dumps(schema_hint, ensure_ascii=False)}\n\n"
        )})

        self.logger.info("llm_call_thought_start", step=next_step.position)
        response = await litellm.acompletion(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            tools=self.tools_schema,
            tool_choice="auto",
        )

        raw_content = response.choices[0].message.content
        self.message_history.add_message(raw_content, "assistant")

        # Robust parsing: handle accidental multiple JSON objects
        def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
            objects: List[Dict[str, Any]] = []
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return [parsed]
                if isinstance(parsed, list):
                    return [obj for obj in parsed if isinstance(obj, dict)]
            except Exception:
                pass

            depth = 0
            in_str = False
            escape = False
            start_idx: Optional[int] = None
            for i, ch in enumerate(text):
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                else:
                    if ch == '"':
                        in_str = True
                        continue
                    if ch == '{':
                        if depth == 0:
                            start_idx = i
                        depth += 1
                        continue
                    if ch == '}':
                        depth -= 1
                        if depth == 0 and start_idx is not None:
                            segment = text[start_idx:i+1]
                            try:
                                obj = json.loads(segment)
                                if isinstance(obj, dict):
                                    objects.append(obj)
                            except Exception:
                                pass
                            start_idx = None
                        continue
            return objects

        candidates = _extract_json_objects(raw_content or "")
        chosen: Optional[Dict[str, Any]] = None
        for obj in candidates:
            try:
                if int(obj.get("next_step_ref")) == int(next_step.position):
                    chosen = obj
                    break
            except Exception:
                continue
        if not chosen and candidates:
            chosen = candidates[0]

        self.logger.info("llm_call_thought_end", step=next_step.position)
        if chosen:
            return Thought.from_json(chosen)
        # Fallback to original content (may still raise, which is fine to surface)
        return Thought.from_json(raw_content)


    async def _decide_next_action(self, thought: Thought, next_step: TodoItem) -> Action:
        """
        Decides the next action for the next step based on the thought.
        """
        thought_action = thought.action
        if thought_action.type == ActionType.TOOL:
            return Action(
                type=ActionType.TOOL,
                tool=thought_action.tool,
                input=thought_action.input)
        elif thought_action.type == ActionType.ASK:
            return Action(
                type=ActionType.ASK,
                tool=thought_action.tool,
                input=thought_action.input,
                question=thought_action.question)
        elif thought_action.type == ActionType.DONE:
            return Action(
                type=ActionType.DONE,
                tool=thought_action.tool,
                input=thought_action.input,
                message=thought_action.message)
        elif thought_action.type == ActionType.PLAN:
            return Action(
                type=ActionType.PLAN,
                tool=thought_action.tool,
                input=thought_action.input)
        elif thought_action.type == ActionType.ERR:
            return Action(
                type=ActionType.ERR,
                tool=thought_action.tool,
                input=thought_action.input)
        else:
            raise ValueError(f"Invalid action type: {thought_action.type}")


    async def _execute_action(self, action: Action) -> Dict[str, Any]:
        """
        Executes the action for the next step.
        """
        if action.type == ActionType.TOOL:            
            tool = self._get_tool(action.tool)
            if not tool:
                raise ValueError(f"Tool '{action.tool}' not found")
            self.logger.info("tool_execute_start", tool=action.tool)
            return await tool.execute(**action.input)
            
        elif action.type == ActionType.ASK:
            question_text = action.question or action.input.get("question") or "I need additional information to proceed."
            return {"success": False, "requires_user": True, "question": question_text}
        elif action.type == ActionType.DONE:
            pass
        elif action.type == ActionType.PLAN:
            pass
        elif action.type == ActionType.ERR:
            pass
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