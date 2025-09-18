# An Agent class

from dataclasses import field
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, AsyncIterator, Dict, List, Optional
from attr import dataclass
import litellm

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

Operating principles:
- Plan-first: create/update a concise Todo List; clarify blocking questions first.
- Be deterministic, keep outputs minimal & actionable.
- After each tool call, update state; avoid loops; ask for help on blockers.

Decision policy:
- Prefer available tools; when in doubt, ask the user for clarification rather than making assumptions.
- Stop when acceptance criteria for the mission are met.

Output style:
- Short, structured, CLI-friendly status lines.
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

    @staticmethod
    def from_json(json_str: str) -> "Action":
        """
        Creates an Action object from a JSON string.
        """
        data = json.loads(json_str)
        return Action(
            type=ActionType(data["type"]),
            tool=data["tool"],
            input=data["input"])


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

    async def execute(self, user_message: str, session_id: str) -> AsyncIterator[AgentEvent]:
        """
        Executes the agent with the given user message.
        Before executing the agent, the agent will plan the tasks to complete the mission.
        If the agent needs to ask the user for more information, the agent will ask the user for the information.
        If the agent needs to use a tool, the agent will use the tool to complete the task.
        If the agent needs to complete a task, the agent will complete the task.
        If the agent needs to replan the tasks, the agent will replan the tasks.
        If the agent needs to complete the mission, the agent will complete the mission.
        
        Args:
            user_message: The user message to execute the agent with.
            session_id: The execution id for the agent. This is used to identify the actual plan, steps, and result, state of the agent

        Returns:
            An asynchronous iterator of AgentEvent objects.
        """

        # get the current state of the agent
        self.state = await self.state_manager.load_state(session_id)

        # if we were writing on an answer, consume it right now
        if self.state.get("preding_question"):
            answer = user_message.strip()
            pending_question = self.state.pop("pending_question")
            # store the answer by key for later parameter filling
            answers = self.state.setdefault("answers", {})
            answers[pending_question["answer_key"]] = answer
            await self.state_manager.save_state(session_id, self.state)
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, data={"answers": answers})


        self.message_history.add_message(user_message, "user")
        self.state["message_history"] = self.message_history.messages
        self.state["last_user_message"] = user_message
        self.state["mission"] = self.mission

        # save the state
        await self.state_manager.save_state(session_id, self.state)

        # Before a plan is created, we shall check if there are some open questions that need to be answered

        # get the current todolist
        todolist = await self._create_or_get_todolist(session_id, self.state)

        # now that we have the todolist, we can execute the todolist in a ReAct loop
        for next_step in todolist.items:
            # 1. generate a thought
            thought = await self._generate_thought(next_step)
            # 2. decide the next action
            action = await self._decide_next_action(thought, next_step)
            # 3. execute the action
            observation = await self._execute_action(action)
            # 4. update the state with the observation
            self.state["last_observation"] = observation
            # 5. update the state of the next step
            if observation.get("success"):
                next_step.state = TaskStatus.COMPLETED
            else:
                next_step.state = TaskStatus.FAILED
            # 6. save the state
            await self.state_manager.save_state(session_id, self.state)


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

            return todolist
        else:
            todolist = await self.todo_list_manager.load_todolist(todolist_id)                
            return todolist


    def _get_tools_description(self) -> str:
        """
        Gets the description of the tools available.
        """
        return "\n".join([ f"- {tool.name}: {tool.description}" for tool in self.tools])


    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Gets the schema of the tools available which can be used as a function calling schema for the LLM.
        """
        return [tool.function_tool_schema for tool in self.tools]


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
        messages = self.message_history.get_last_n_messages(2)

        messages.append({"role": "user", "content": (
            "You are the Planning & Action Selector.\n"
            "Pick exactly one next action for the next_step below.\n"
            f"NEXT_STEP:\n{next_step.to_json()}\n\n"
            "Prefer tools; ask_user only if info is missing.\n"
            "Return STRICT JSON only (no extra text) matching this schema:\n"
            f"{json.dumps(schema_hint, ensure_ascii=False)}\n\n"
        )})

        response = await litellm.acompletion(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            tools=self.tools_schema,
            tool_choice="auto",
        )

        self.message_history.add_message(response.choices[0].message.content, "assistant")

        return Thought.from_json(response.choices[0].message.content)


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
                input=thought_action.input)
        elif thought_action.type == ActionType.DONE:
            return Action(
                type=ActionType.DONE,
                tool=thought_action.tool,
                input=thought_action.input)
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


    async def _execute_action(self, action: Action) -> str:
        """
        Executes the action for the next step.
        """
        if action.type == ActionType.TOOL:            
            tool = self._get_tool(action.tool)
            if not tool:
                raise ValueError(f"Tool '{action.tool}' not found")

            return await tool.execute(**action.input)
            
        elif action.type == ActionType.ASK:
            pass
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
    mission = None

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
    user_message = "Create a new directory named 'my-test-dir' and add a README.txt file inside it containing a hello_world code example."

    print(f"Starting Agent execute() with session_id={session_id}")
    try:
        asyncio.run(agent.execute(user_message=user_message, session_id=session_id))
        print("Agent execute() finished (up to current implementation).")
    except Exception as exc:
        print(f"Agent execution failed: {exc}")


if __name__ == "__main__":
    main()