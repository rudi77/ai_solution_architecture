# An Agent class

from typing import Any, Dict, List, Optional

from capstone.agent_v2.planning.planner import ExecutionPlan, PlanManager
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tool import Tool

GENERIC_SYSTEM_PROMPT = """
You are a ReAct-style execution agent.

Operating principles:
- Plan-first: create/update a concise Todo List; clarify blocking questions first.
- Be deterministic, keep outputs minimal & actionable.
- After each tool call, update state; avoid loops; ask for help on blockers.

Decision policy:
- Prefer available tools; ask user only for truly blocking info.
- Stop when acceptance criteria for the mission are met.

Output style:
- Short, structured, CLI-friendly status lines.
"""

class Agent:
    def __init__(self, 
        name: str, 
        description: str, 
        system_prompt: Optional[str],
        mission: Optional[str],
        tools: List[Tool],
        planner: PlanManager,
        state_manager: StateManager):
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
        self.planner = planner
        self.state_manager = state_manager

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
        await self.state_manager.save_state(session_id, state)

        # get the current plan
        plan = await self.__get_plan(session_id, state)
        if not plan:
            return {
                "success": False,
                "error": "No plan found"
            }


        # now that we have the plan, we can execute the plan
        for next_step in plan.steps:
           continue




    async def __get_plan(self, session_id: str, state: Dict[str, Any]) -> Optional[ExecutionPlan]:    
        plan_id = state.get("plan_id")
        # check if a plan has already been created for the mission
        if not plan_id:
            # create a new plan for the mission
            message_history = state.get("message_history")
            plan = await self.planner.create_plan(self.mission, self.__get_planning_context(session_id, message_history))
            plan_id = plan.id
            state["plan_id"] = plan_id
            await self.state_manager.save_state(session_id, state)
            return plan
        else:
            plan = await self.planner.load_plan(plan_id)
            return plan


    def __get_planning_context(self, session_id: str, message_history: List[Dict[str, Any]]) -> Dict[str, Any]:
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

        