# An Agent class

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from attr import dataclass
import litellm

from capstone.agent_v2.planning.todolist import TodoList, TodoListManager
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

def build_system_prompt(base: str, mission: str, todo_list: Optional[str] = "") -> str:
    """
    Build the system prompt from base, mission, and todo list sections.

    Args:
        base (str): The static base instructions (timeless context).
        mission (str): The agent's mission or current objective.
        todo_list (str, optional): Current todo list, may be empty. Defaults to "".

    Returns:
        str: Final system prompt ready for use.
    """
    prompt = f"""<Base>
{base.strip()}
</Base>

<Mission>
{mission.strip()}
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
        todo_list: TodoListManager,
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
        self.todo_list = todo_list
        self.state_manager = state_manager
        self.message_history = MessageHistory(build_system_prompt(system_prompt, mission))


    async def execute(self, user_message: str, session_id: str, message_history: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        """

        # get the current state of the agent
        state = await self.state_manager.load_state(session_id)

        # update message history in state
        state["message_history"] = message_history
        state["last_user_message"] = user_message
        state["mission"] = self.mission

        # save the state
        await self.state_manager.save_state(session_id, state)

        # Before a plan is created, we shall check if there are some open questions that need to be answered

        # get the current todolist
        todolist = await self._create_or_get_todolist(session_id, state)

        # now that we have the todolist, we can execute the todolist in a ReAct loop
        for next_step in todolist.steps:
           # 1. generate a thought
           thought = await self._generate_thought(next_step)
           # 2. decide the next action
           action = await self._decide_next_action(thought, next_step)
           # 3. execute the action
           observation = await self._execute_action(action)

           await self.state_manager.save_state(session_id, state)


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
        if not todolist_id:
            # create a new plan for the mission
            message_history = state.get("message_history")
            plan = await self.todo_list.create_todolist(self.mission, self._get_planning_context(session_id, message_history))
            todolist_id = plan.id
            state["todolist_id"] = todolist_id
            await self.state_manager.save_state(session_id, state)
            return plan
        else:
            plan = await self.todo_list.load_todolist(todolist_id)                
            return plan

    def _get_planning_context(self, session_id: str, message_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Gets the planning context for the agent. Which consists of:
        - The Agent's name
        - The Agent's description
        - The Agent's system prompt
        - The Agent's history

        Args:
            session_id: The session id for the agent.
            message_history: The message history for the agent.
        """

        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "history": message_history,
        }            

    async def _generate_thought(self, next_step: str) -> str:
        """
        Generates a thought for the next step.
        """
        pass

    async def _decide_next_action(self, thought: str, next_step: str) -> str:
        """
        Decides the next action for the next step.
        """
        pass

    async def _execute_action(self, action: str) -> str:
        """
        Executes the action for the next step.
        """
        pass

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

        system_prompt = GENERIC_SYSTEM_PROMPT
        work_dir = Path(work_dir)
        work_dir.mkdir(exist_ok=True)

        # todolist directory is work_dir/todolists
        todolist_dir = work_dir / "todolists"
        todolist_dir.mkdir(exist_ok=True)
        planner = TodoListManager(base_dir=todolist_dir)

        # state directory is work_dir/states
        state_dir = work_dir / "states"
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(base_dir=state_dir)

        return Agent(name, description, system_prompt, mission, tools, planner, state_manager, llm)
