# An Agent class

from dataclasses import field, asdict, dataclass
import asyncio
import os
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, AsyncIterator, Dict, List, Optional
import uuid
# Removed: from attr import asdict, dataclass - using dataclasses instead
import structlog

from capstone.agent_v2.planning.todolist import TaskStatus, TodoItem, TodoList, TodoListManager
from capstone.agent_v2.replanning import (
    ReplanStrategy,
    StrategyType,
    REPLAN_PROMPT_TEMPLATE,
    validate_strategy,
    extract_failure_context,
    STRATEGY_GENERATION_TIMEOUT,
)
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool

LESSON_EXTRACTION_PROMPT = """
Analyze this task execution history and extract a generalizable lesson.

**Task Description:** {task_description}

**Execution History:**
{execution_history}

**What happened:**
- Attempts: {attempt_count}
- Initial failure: {initial_error}
- Final success: {final_result}
- Tools used: {tools_used}

Extract a lesson that would help in similar future situations.
Focus on: what failed, what worked, why it worked, how to recognize similar situations.

Respond with JSON:
{{
  "context": "Brief description of situation type (2-3 sentences)",
  "what_failed": "What approach didn't work and why",
  "what_worked": "What approach succeeded and why",
  "lesson": "Generalizable takeaway for future tasks",
  "tool_name": "Primary tool involved (if relevant)",
  "confidence": 0.0-1.0
}}
"""

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
    SUMMARY_THRESHOLD = 20  # Reduced from 40 to compress more aggressively
    
    def __init__(self, system_prompt: str, llm_service: LLMService):
        """
        Initialize message history.
        
        Args:
            system_prompt: The system prompt
            llm_service: LLM service for compression operations
        """
        # Store system prompt as the first message entry
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.messages = [self.system_prompt]
        self.llm_service = llm_service
        self.logger = structlog.get_logger()

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
        """Summarize old messages using LLM service."""
        old_messages = self.messages[1:self.SUMMARY_THRESHOLD]  # Skip system
        
        summary_prompt = f"""Summarize this conversation history concisely:

{json.dumps(old_messages, indent=2)}

Provide a 2-3 paragraph summary of key decisions, results, and context."""
        
        try:
            # Use LLMService
            result = await self.llm_service.complete(
                messages=[{"role": "user", "content": summary_prompt}],
                model="main",
                temperature=0
            )
            
            if not result.get("success"):
                self.logger.error(
                    "compression_failed",
                    error=result.get("error")
                )
                # If compression fails, just keep the recent messages
                self.messages = [self.system_prompt] + self.messages[-self.SUMMARY_THRESHOLD:]
                return
            
            summary = result["content"]
            
            self.messages = [
                self.system_prompt,
                {"role": "system", "content": f"[Previous context summary]\n{summary}"},
                *self.messages[self.SUMMARY_THRESHOLD:]
            ]
        except Exception as e:
            self.logger.error("compression_exception", error=str(e))
            # If compression fails, just keep the recent messages
            self.messages = [self.system_prompt] + self.messages[-self.SUMMARY_THRESHOLD:]

    def get_last_n_messages(self, n: int) -> List[Dict[str, Any]]:
        """
        Gets the last n message pairs (user and assistant) in chronological order,
        always including the system prompt as the first message. Also includes
        any trailing incomplete user message for conversational context.

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
        has_trailing = len(body) % 2 == 1  # Odd number means trailing message

        if num_pairs == 0:
            # No complete pairs, but include trailing message if present
            return [self.system_prompt] + (body if has_trailing else [])

        if n >= num_pairs:
            # Return all complete pairs plus any trailing message
            return [self.system_prompt] + body

        # Return last n pairs plus any trailing message
        start_index = len(body) - (n * 2) - (1 if has_trailing else 0)
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


class ApprovalPolicy(str, Enum):
    """Policy for handling approval requests for sensitive operations."""
    PROMPT = "prompt"              # Ask user for each approval (default)
    AUTO_APPROVE = "auto_approve"  # Approve all automatically (logs warning)
    AUTO_DENY = "auto_deny"        # Deny all automatically (logs error)

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
        Creates a Thought object from a JSON string with robust error handling.
        """
        import re
        
        # Accept both JSON string and already-parsed dict
        if isinstance(json_str, (str, bytes, bytearray)):
            # Convert bytes to string if needed
            if isinstance(json_str, (bytes, bytearray)):
                json_str = json_str.decode('utf-8', errors='replace')
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Strategy 1: Try to extract JSON from markdown code blocks
                json_match = re.search(r'```json\s*\n(.*?)\n```', 
                                      json_str, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass  # Fall through to next strategy
                else:
                    # Strategy 2: Try to fix truncated JSON by finding last complete object
                    try:
                        # Find the last valid closing brace
                        last_brace = json_str.rfind('}')
                        if last_brace > 0:
                            truncated = json_str[:last_brace + 1]
                            data = json.loads(truncated)
                        else:
                            raise e
                    except (json.JSONDecodeError, ValueError):
                        # Strategy 3: Try to extract just the action object if present
                        action_match = re.search(
                            r'"action"\s*:\s*\{[^}]*"type"\s*:\s*"([^"]+)"',
                            json_str
                        )
                        if action_match:
                            # Build minimal valid thought with extracted action type
                            action_type = action_match.group(1)
                            data = {
                                "step_ref": 0,
                                "rationale": "JSON parsing recovered from truncated response",
                                "action": {
                                    "type": action_type,
                                    "tool": None,
                                    "tool_input": {}
                                },
                                "expected_outcome": "Recovered from parsing error",
                                "confidence": 0.5
                            }
                        else:
                            # All strategies failed - raise with context
                            raise ValueError(
                                f"Invalid JSON in Thought: {e}. "
                                f"Content preview: {json_str[:500]}..."
                            ) from e
        elif isinstance(json_str, dict):
            data = json_str
        else:
            raise TypeError("Thought.from_json expects str|bytes|bytearray|dict")
        
        return Thought(
            step_ref=data.get("step_ref") or data.get("next_step_ref"),
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


def build_system_prompt(system_prompt: str, mission: Optional[str], tools_description: str) -> str:
    """
    Build the system prompt from base, mission, and tools description.
    
    Story CONV-HIST-002: Mission is now optional to support mission-agnostic system prompts
    that remain stable across multiple queries.

    Args:
        system_prompt (str): The static base instructions (timeless context).
        mission (Optional[str]): The agent's mission or current objective. 
            Can be None for mission-agnostic prompts (recommended for multi-turn conversations).
        tools_description (str): The description of the tools available.

    Returns:
        str: Final system prompt ready for use.
    """
    # Start with base prompt
    prompt_parts = [f"<Base>\n{system_prompt.strip()}\n</Base>"]
    
    # Only add mission section if mission is provided (backward compatibility)
    if mission:
        prompt_parts.append(f"<Mission>\n{mission.strip()}\n</Mission>")
    
    # Add tools description
    if tools_description:
        prompt_parts.append(f"<ToolsDescription>\n{tools_description.strip()}\n</ToolsDescription>")
    
    return "\n\n".join(prompt_parts)



class Agent:
    def __init__(self, 
        name: str, 
        description: str, 
        system_prompt: Optional[str],
        mission: Optional[str],
        tools: List[Tool],
        todo_list_manager: TodoListManager,
        state_manager: StateManager,
        llm_service: LLMService,
        llm=None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.PROMPT,
        memory_manager=None,
        enable_lesson_extraction: bool = True):
        """
        Initializes the Agent with the given name, description, system prompt, mission, tools, and LLM service.
        
        Args:
            name: The name of the agent.
            description: The description of the agent.
            system_prompt: The system prompt for the agent. This is the generic part of the agent's system prompt.
            mission: The mission for the agent. This is a collection of tasks that the agent needs to complete.
            tools: The tools for the agent. This is a collection of tools that the agent can use to complete the tasks.
            todo_list_manager: The todo list manager for the agent. This is the manager that creates and updates todo lists.
            state_manager: The state manager for the agent. This is the state manager that the agent uses to save the state of the agent.
            llm_service: LLM service for completions
            llm: (Deprecated) Legacy LLM parameter for backward compatibility
            approval_policy: Policy for handling approval requests (default: PROMPT)
            memory_manager: Memory manager for learned skills (optional)
            enable_lesson_extraction: Enable automatic lesson extraction from execution outcomes
        """

        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        # Store system prompt template for potential rebuilding (Story CONV-HIST-002)
        self.system_prompt_template = system_prompt
        self.mission = mission
        self.tools = tools
        self.tools_description = self._get_tools_description()
        self.tools_schema = self._get_tools_schema()
        self.todo_list_manager = todo_list_manager
        self.state_manager = state_manager
        self.llm_service = llm_service
        self.approval_policy = approval_policy
        self.memory_manager = memory_manager
        self.enable_lesson_extraction = enable_lesson_extraction
        self._planning_memories = []  # Track memories used in planning (Story 4.3)
        self.state = None
        # Initialize with mission-agnostic system prompt (Story CONV-HIST-002)
        # Mission is stored in self.mission but not embedded in system prompt
        # User queries will be added as natural conversation messages
        self.message_history = MessageHistory(
            build_system_prompt(system_prompt, None, self.tools_description),
            llm_service
        )
        self.logger = structlog.get_logger().bind(agent=name)


    async def execute(self, user_message: str, session_id: str) -> AsyncIterator[AgentEvent]:
        """
        Executes the agent with the given user message using ReAct architecture:
        1) Load state
        2) Detect if completed todolist should be reset for new query
        3) Reset mission and todolist if needed (multi-turn support)
        4) Set mission (only on first call or after reset)
        5) Add user message to conversation history
        6) Answer pending question (if any)
        7) Create plan (if not exists)
        8) Run ReAct loop

        Args:
            user_message: The user message to execute the agent.
            session_id: The session id to execute the agent.

        Returns:
            An async iterator of AgentEvent.
        """
        # 1. State laden
        self.state = await self.state_manager.load_state(session_id)
        # Initialize approval state (Story 2.2)
        self.state.setdefault("approval_cache", {})
        self.state.setdefault("trust_mode", False)
        self.state.setdefault("approval_history", [])
        
        self.logger.info(
            "execute_start", 
            session_id=session_id,
            todolist_id_in_state=self.state.get("todolist_id"),
            mission_set=self.mission is not None
        )

        # 2. Check for completed todolist on new input
        # This detects when user starts a new query after completing previous one
        should_reset_mission: bool = False
        previous_todolist_id: Optional[str] = None
        
        # Only check if NOT answering a pending question
        if not self.state.get("pending_question"):
            todolist_id: Optional[str] = self.state.get("todolist_id")
            
            if todolist_id:
                try:
                    # Load existing todolist to check completion status
                    existing_todolist: TodoList = await self.todo_list_manager.load_todolist(todolist_id)
                    
                    # Check if all tasks are completed
                    if self._is_plan_complete(existing_todolist):
                        should_reset_mission = True
                        previous_todolist_id = todolist_id
                        self.logger.info(
                            "completed_todolist_detected_on_new_input",
                            session_id=session_id,
                            todolist_id=todolist_id,
                            will_reset=True
                        )
                except FileNotFoundError:
                    # Todolist file doesn't exist, will create new one anyway
                    self.logger.warning(
                        "todolist_file_not_found",
                        session_id=session_id,
                        todolist_id=todolist_id
                    )
        
        # 3. Execute mission reset if needed (Story 2: Multi-turn support)
        if should_reset_mission:
            self.logger.info(
                "resetting_mission_preserving_conversation",
                session_id=session_id,
                previous_mission_preview=self.mission[:100] if self.mission else None,
                previous_todolist_id=previous_todolist_id,
                new_query_preview=user_message[:100],
                conversation_preserved=True,
                message_count=len(self.message_history.messages)
            )
            
            # Clear mission and todolist reference to allow fresh start
            # NOTE: Conversation history is preserved across resets (CONV-HIST-001)
            self.mission = None
            self.state.pop("todolist_id", None)
            
            # Trigger history compression if message count exceeds threshold (CONV-HIST-003)
            message_count = len(self.message_history.messages)
            if message_count > self.message_history.SUMMARY_THRESHOLD:
                self.logger.info(
                    "triggering_history_compression",
                    session_id=session_id,
                    message_count_before=message_count,
                    threshold=self.message_history.SUMMARY_THRESHOLD
                )
                
                try:
                    await self.message_history.compress_history_async()
                    
                    new_message_count = len(self.message_history.messages)
                    self.logger.info(
                        "history_compression_complete",
                        session_id=session_id,
                        message_count_before=message_count,
                        message_count_after=new_message_count,
                        messages_reduced=message_count - new_message_count
                    )
                except Exception as e:
                    self.logger.error(
                        "history_compression_failed",
                        session_id=session_id,
                        error=str(e),
                        message_count=message_count
                    )
                    # Continue execution despite compression failure
            
            # Persist state changes
            try:
                await self.state_manager.save_state(session_id, self.state)
            except Exception as e:
                self.logger.error(
                    "state_save_failed_during_reset",
                    session_id=session_id,
                    error=str(e)
                )
                # Continue execution despite save failure
            
            # Notify CLI that reset occurred
            yield AgentEvent(
                type=AgentEventType.STATE_UPDATED,
                data={
                    "mission_reset": True,
                    "reason": "completed_todolist_detected",
                    "previous_todolist_id": previous_todolist_id,
                    "conversation_preserved": True,
                    "message_count": len(self.message_history.messages)
                }
            )
            
            self.logger.info("mission_reset_complete", session_id=session_id)
        
        # 4. Mission setzen (nur beim ersten Call oder nach Reset)
        if self.mission is None:
            self.mission = user_message
            self.logger.info("mission_set", session_id=session_id, mission_preview=self.mission[:100])

        # 5. Add user message to conversation history (Story CONV-HIST-002)
        # This ensures LLM can see the actual user query in conversation context
        self.message_history.add_message(user_message, "user")
        self.logger.info(
            "user_message_added_to_history",
            session_id=session_id,
            message_preview=user_message[:100],
            total_messages=len(self.message_history.messages)
        )

        # 5.5. Check for set-policy command (Story 2.3)
        if user_message.strip().lower().startswith("set-policy"):
            parts = user_message.strip().split(maxsplit=1)
            if len(parts) == 2:
                policy_str = parts[1].strip().lower().replace("-", "_")
                try:
                    new_policy = ApprovalPolicy(policy_str)
                    old_policy = self.approval_policy
                    self.approval_policy = new_policy
                    
                    # Log policy change
                    self.logger.info(
                        "approval_policy_changed",
                        session_id=session_id,
                        old_policy=old_policy.value,
                        new_policy=new_policy.value
                    )
                    
                    # Audit log
                    record = {
                        "timestamp": datetime.now().isoformat(),
                        "action": "policy_change",
                        "old_policy": old_policy.value,
                        "new_policy": new_policy.value
                    }
                    self.state.setdefault("approval_history", []).append(record)
                    await self.state_manager.save_state(session_id, self.state)
                    
                    yield AgentEvent(
                        type=AgentEventType.STATE_UPDATED,
                        data={
                            "policy_changed": True,
                            "old_policy": old_policy.value,
                            "new_policy": new_policy.value,
                            "message": f"Approval policy changed to {new_policy.value}"
                        }
                    )
                    return
                except ValueError:
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        data={
                            "error": f"Invalid policy: {parts[1]}. Valid options: prompt, auto-approve, auto-deny"
                        }
                    )
                    return
            else:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    data={"error": "Usage: set-policy [prompt|auto-approve|auto-deny]"}
                )
                return

        # 6. Pending Question beantworten (falls vorhanden)
        if self.state.get("pending_question"):
            answer_key = self.state["pending_question"]["answer_key"]
            self.state.setdefault("answers", {})[answer_key] = user_message
            self.state.pop("pending_question")
            await self.state_manager.save_state(session_id, self.state)
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, 
                            data={"answer_received": answer_key})
            self.logger.info("answer_received", session_id=session_id, answer_key=answer_key)
        
        # 7. Plan erstellen (falls noch nicht vorhanden)
        todolist_existed = self.state.get("todolist_id") is not None
        self.logger.info(
            "before_get_or_create_plan",
            session_id=session_id,
            todolist_existed=todolist_existed,
            todolist_id_in_state=self.state.get("todolist_id"),
            mission_preview=self.mission[:100] if self.mission else None
        )
        todolist = await self._get_or_create_plan(session_id)
        self.logger.info(
            "after_get_or_create_plan",
            session_id=session_id,
            todolist_id=todolist.todolist_id,
            num_items=len(todolist.items),
            first_item_status=todolist.items[0].status.value if todolist.items else None
        )

        # Emit todolist created event if it was just created
        if not todolist_existed:
            yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                           data={"todolist_created": True,
                                 "todolist": todolist.to_markdown(),
                                 "items": len(todolist.items)})

        # 8. ReAct Loop
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
                answers=answers,
                memory_manager=self.memory_manager  # NEW: Pass memory manager (Story 4.3)
        )
        
        # Store retrieved memories for success tracking (Story 4.3)
        if hasattr(todolist, 'retrieved_memories') and todolist.retrieved_memories:
            self._planning_memories = todolist.retrieved_memories

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
                # Story 2.2 & 2.3: Approval Gate with Policy
                tool_obj = self._get_tool(thought.action.tool)
                if tool_obj and tool_obj.requires_approval:
                    # Request approval based on policy
                    approval_decision = self._request_approval(tool_obj, thought.action.tool_input)
                    
                    if approval_decision is False:
                        # Denied (AUTO_DENY policy or user denied)
                        current_step.status = TaskStatus.SKIPPED
                        self.logger.info("step_skipped_approval_denied", session_id=session_id, step=current_step.position)
                        yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                       data={"step_skipped": current_step.position,
                                             "reason": "approval_denied"})
                        await self.state_manager.save_state(session_id, self.state)
                        await self.todo_list_manager.update_todolist(todolist)
                        continue
                    
                    elif approval_decision is None:
                        # Need user input (PROMPT policy)
                        approval_key = f"approval_step_{current_step.position}_{tool_obj.name}_{current_step.attempts}"
                        user_answer = self.state.get("answers", {}).get(approval_key)
                        
                        if user_answer:
                            # Process the answer
                            if not self._process_approval_response(user_answer, tool_obj, current_step.position):
                                # Denied
                                current_step.status = TaskStatus.SKIPPED
                                self.logger.info("step_skipped_approval_denied", session_id=session_id, step=current_step.position)
                                yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                               data={"step_skipped": current_step.position,
                                                     "reason": "approval_denied"})
                                await self.state_manager.save_state(session_id, self.state)
                                await self.todo_list_manager.update_todolist(todolist)
                                continue
                            # If approved, proceed to execution
                        else:
                            # Request approval
                            prompt = self._build_approval_prompt(tool_obj, thought.action.tool_input)
                            
                            self.state["pending_question"] = {
                                "answer_key": approval_key,
                                "question": prompt,
                                "for_step": current_step.position
                            }
                            await self.state_manager.save_state(session_id, self.state)
                            
                            yield AgentEvent(type=AgentEventType.ASK_USER, 
                                            data={"question": prompt})
                            return  # Pause execution
                    # If approval_decision is True, proceed to execution

                # Tool ausführen
                observation = await self._execute_tool_safe(thought.action)
                
                # Runtime-Felder füllen
                current_step.chosen_tool = thought.action.tool
                current_step.tool_input = thought.action.tool_input
                current_step.execution_result = observation
                
                # NEW: Track execution history for lesson extraction (Story 4.2)
                current_step.execution_history.append({
                    "tool": thought.action.tool,
                    "success": observation.get("success", False),
                    "error": observation.get("error")
                })
                current_step.attempts += 1
                
                # Status updaten
                if observation.get("success"):
                    # Acceptance Criteria prüfen
                    if await self._check_acceptance(current_step, observation):
                        current_step.status = TaskStatus.COMPLETED
                        self.logger.info("step_completed", session_id=session_id,
                                       step=current_step.position)
                        
                        # NEW: Post-execution lesson extraction (Story 4.2)
                        if self.enable_lesson_extraction and self.memory_manager:
                            if self._has_learning_pattern(current_step):
                                lesson = await self._extract_lesson(current_step)
                                if lesson:
                                    await self.memory_manager.store_memory(lesson)
                                    self.logger.info("Lesson extracted and stored", lesson_id=lesson.id)
                        
                        # NEW: Memory success tracking (Story 4.3)
                        if self.memory_manager and self._planning_memories:
                            for memory in self._planning_memories:
                                await self.memory_manager.update_success_count(memory.id, increment=1)
                                self.logger.debug("Memory helped with successful execution", memory_id=memory.id)
                        
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
                    # Tool execution failed - attempt automatic replanning before marking as FAILED
                    replanned = False
                    if current_step.replan_count < 2:
                        self.logger.info("tool_failed_attempting_replan", 
                                       session_id=session_id,
                                       step=current_step.position,
                                       replan_attempt=current_step.replan_count + 1)
                        
                        replan_success, replan_summary = await self._attempt_automatic_replan(
                            current_step, 
                            observation
                        )
                        
                        if replan_success:
                            self.logger.info("replan_successful", 
                                           session_id=session_id,
                                           step=current_step.position,
                                           summary=replan_summary)
                            replanned = True
                            # Reload todolist to get updated plan
                            todolist = await self.todo_list_manager.load_todolist(self.todolist_id)
                            yield AgentEvent(type=AgentEventType.STATE_UPDATED,
                                           data={"step_replanned": current_step.position,
                                                 "summary": replan_summary})
                        else:
                            self.logger.warning("replan_failed", 
                                              session_id=session_id,
                                              step=current_step.position,
                                              summary=replan_summary)
                    
                    # Only mark as FAILED if not replanned
                    if not replanned:
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
                
                # Mark all remaining pending steps as SKIPPED to allow mission reset on next query
                for step in todolist.items:
                    if step.status == TaskStatus.PENDING:
                        step.status = TaskStatus.SKIPPED
                        self.logger.info("step_skipped_on_done", session_id=session_id,
                                       step=step.position,
                                       reason="early_completion")

                # CRITICAL: Save state and todolist BEFORE breaking to persist SKIPPED status
                await self.state_manager.save_state(session_id, self.state)
                await self.todo_list_manager.update_todolist(todolist)
                self.logger.info("state_and_todolist_saved_on_early_completion", 
                               session_id=session_id,
                               todolist_id=todolist.todolist_id)

                # Emit final answer before breaking
                final_answer = thought.action.summary if hasattr(thought.action, 'summary') else "Task completed"
                yield AgentEvent(type=AgentEventType.COMPLETE,
                                data={"message": final_answer, "summary": final_answer})
                
                # Compress history after task completion to avoid context pollution
                message_count = len(self.message_history.messages)
                if message_count > self.message_history.SUMMARY_THRESHOLD:
                    self.logger.info(
                        "compressing_history_after_task_completion",
                        session_id=session_id,
                        message_count=message_count
                    )
                    try:
                        await self.message_history.compress_history_async()
                        self.logger.info(
                            "history_compressed_after_task",
                            session_id=session_id,
                            new_message_count=len(self.message_history.messages)
                        )
                    except Exception as e:
                        self.logger.error(
                            "history_compression_failed_after_task",
                            session_id=session_id,
                            error=str(e)
                        )
                
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
        
        # Fertig - compress history after completing all tasks
        message_count = len(self.message_history.messages)
        if message_count > self.message_history.SUMMARY_THRESHOLD:
            self.logger.info(
                "compressing_history_after_all_tasks",
                session_id=session_id,
                message_count=message_count
            )
            try:
                await self.message_history.compress_history_async()
                self.logger.info(
                    "history_compressed_after_all_tasks",
                    session_id=session_id,
                    new_message_count=len(self.message_history.messages)
                )
            except Exception as e:
                self.logger.error(
                    "history_compression_failed_after_all_tasks",
                    session_id=session_id,
                    error=str(e)
                )
        
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

        # Get the last 2 message pairs from history (reduced from 4 to avoid context pollution)
        messages = self.message_history.get_last_n_messages(2)

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
            "- ALWAYS populate `expected_outcome` with a concise sentence describing what you expect after executing the action.\n"
            "- When you choose the `complete` action, you must already have produced the final answer (e.g., via `llm_generate`) and include a clear summary in `action.summary`.\n"
            "- **IMPORTANT**: Keep all text fields CONCISE (max 200 chars each) to ensure valid JSON.\n"
            "- For tool_input fields with long text (prompts, code), keep them under 1000 characters.\n"
            "Return STRICT JSON only (no extra text) matching this schema:\n"
            f"{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        )})

        self.logger.info("llm_call_thought_start", step=current_step.position)
        
        # Use LLMService
        result = await self.llm_service.complete(
            messages=messages,
            model="main",
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        if not result.get("success"):
            self.logger.error(
                "thought_generation_failed",
                step=current_step.position,
                error=result.get("error")
            )
            raise RuntimeError(f"LLM completion failed: {result.get('error')}")
        
        raw_content = result["content"]
        self.message_history.add_message(raw_content, "assistant")

        self.logger.info(
            "llm_call_thought_end",
            step=current_step.position,
            tokens=result.get("usage", {}).get("total_tokens", 0)
        )
        
        try:
            return Thought.from_json(raw_content)
        except Exception as e:
            self.logger.error(
                "thought_parse_failed", 
                step=current_step.position, 
                error=str(e),
                raw_content_preview=raw_content[:500] if raw_content else None
            )
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


    def _request_approval(self, tool: Tool, parameters: Dict) -> Optional[bool]:
        """
        Request approval based on policy.
        
        Returns:
            True: Approved (proceed with execution)
            False: Denied (skip execution)
            None: Need user input (pause execution)
        """
        # Policy-based decisions (Story 2.3)
        if self.approval_policy == ApprovalPolicy.AUTO_APPROVE:
            self.logger.warning(
                "auto_approve_policy",
                tool=tool.name,
                parameters=parameters,
                risk=tool.approval_risk_level.value
            )
            # Log to approval history
            record = {
                "timestamp": datetime.now().isoformat(),
                "tool": tool.name,
                "step": None,
                "risk": tool.approval_risk_level.value,
                "decision": "auto_approved",
                "policy": "AUTO_APPROVE"
            }
            self.state.setdefault("approval_history", []).append(record)
            return True
        
        if self.approval_policy == ApprovalPolicy.AUTO_DENY:
            self.logger.error(
                "auto_deny_policy",
                tool=tool.name,
                parameters=parameters,
                risk=tool.approval_risk_level.value
            )
            # Log to approval history
            record = {
                "timestamp": datetime.now().isoformat(),
                "tool": tool.name,
                "step": None,
                "risk": tool.approval_risk_level.value,
                "decision": "auto_denied",
                "policy": "AUTO_DENY"
            }
            self.state.setdefault("approval_history", []).append(record)
            return False
        
        # PROMPT policy - check existing approvals first
        if self.state.get("trust_mode"):
            return True
        if self.state.get("approval_cache", {}).get(tool.name, False):
            return True
        
        # Need user input
        return None

    def _check_approval_granted(self, tool: Tool) -> bool:
        """Check if tool is approved for execution."""
        if self.state.get("trust_mode"):
            return True
        return self.state.get("approval_cache", {}).get(tool.name, False)

    def _process_approval_response(self, response: str, tool: Tool, step_pos: int) -> bool:
        """Process user response to approval request."""
        response = response.lower().strip()
        
        approved = False
        if response == "trust":
            self.state["trust_mode"] = True
            approved = True
            decision = "trusted"
        elif response in ["y", "yes"]:
            self.state.setdefault("approval_cache", {})[tool.name] = True
            approved = True
            decision = "approved"
        else:
            decision = "denied"
            
        # Audit Log
        record = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool.name,
            "step": step_pos,
            "risk": tool.approval_risk_level.value,
            "decision": decision
        }
        self.state.setdefault("approval_history", []).append(record)
        
        return approved

    def _build_approval_prompt(self, tool: Tool, params: Dict) -> str:
        """Builds the approval prompt."""
        preview = tool.get_approval_preview(**(params or {}))
        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(tool.approval_risk_level.value, "⚠️")
        
        prompt = f"{risk_emoji} Approval Required [{tool.approval_risk_level.value}]\n\n"
        prompt += preview
        prompt += "\n\nApprove this operation? (y/n/trust)"
        return prompt

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
        Adjusts the plan based on current situation (explicit LLM-requested replan).
        
        Args:
            current_step: The step that triggered replanning.
            thought: The thought that suggested replanning.
            todolist: The current todolist.
        
        Returns:
            Updated TodoList.
        """
        # For explicit replan actions from LLM, attempt automatic replanning
        error_context = current_step.execution_result or {}
        success, summary = await self._attempt_automatic_replan(current_step, error_context)
        
        if not success:
            # If replan fails, mark as skipped
            self.logger.warning("replan_failed", step=current_step.position, 
                              rationale=thought.rationale, summary=summary)
            current_step.status = TaskStatus.SKIPPED
        
        return todolist

    async def _attempt_automatic_replan(
        self, 
        failed_step: TodoItem, 
        error_context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Attempt intelligent replanning for a failed TodoItem.
        
        This method implements the core replanning logic:
        1. Generate replan strategy using LLM
        2. Apply strategy to TodoList via TodoListManager
        3. Update MessageHistory with replan context
        4. Log metrics
        
        Args:
            failed_step: The TodoItem that failed execution
            error_context: Error details from tool execution
            
        Returns:
            Tuple of (success: bool, summary: str)
        """
        # Check replan limit
        if failed_step.replan_count >= 2:
            self.logger.warning(
                "replan_limit_exceeded",
                step=failed_step.position,
                replan_count=failed_step.replan_count
            )
            return False, "Max replan attempts (2) exceeded"
        
        self.logger.info(
            "attempting_replan",
            step=failed_step.position,
            attempt=failed_step.replan_count + 1,
            error=str(error_context.get("error", ""))[:100]
        )
        
        # 1. Generate strategy
        strategy = await self.generate_replan_strategy(failed_step, error_context)
        
        if not strategy or strategy.confidence < 0.6:
            return False, "No viable replan strategy found"
        
        # 2. Apply strategy to TodoList via TodoListManager
        success = False
        new_task_ids = []
        error_msg = None
        
        try:
            if strategy.strategy_type == StrategyType.RETRY_WITH_PARAMS:
                # Modify step with new parameters
                success, error_msg = await self.todo_list_manager.modify_step(
                    self.todolist_id,
                    failed_step.position,
                    strategy.modifications
                )
                
            elif strategy.strategy_type == StrategyType.DECOMPOSE_TASK:
                # Split into subtasks
                subtasks = strategy.modifications.get("subtasks", [])
                success, new_task_ids = await self.todo_list_manager.decompose_step(
                    self.todolist_id,
                    failed_step.position,
                    subtasks
                )
                error_msg = f"Created {len(new_task_ids)} subtasks" if success else "Decomposition failed"
                
            elif strategy.strategy_type == StrategyType.SWAP_TOOL:
                # Replace with alternative approach
                success, new_id = await self.todo_list_manager.replace_step(
                    self.todolist_id,
                    failed_step.position,
                    strategy.modifications
                )
                if success:
                    new_task_ids = [new_id] if new_id else []
                error_msg = f"Replaced with new step {new_id}" if success else "Replacement failed"
            else:
                return False, f"Unknown strategy type: {strategy.strategy_type}"
                
        except Exception as e:
            self.logger.error(
                "replan_application_failed",
                step=failed_step.position,
                strategy=strategy.strategy_type.value,
                error=str(e),
                exc_info=True
            )
            return False, f"Failed to apply strategy: {str(e)}"
        
        if not success:
            return False, error_msg or f"Failed to apply {strategy.strategy_type.value}"
        
        # 3. Update MessageHistory with replan context
        replan_msg = f"Replanned step {failed_step.position}: {strategy.strategy_type.value} - {strategy.rationale}"
        self.message_history.add_message(replan_msg, "system")
        
        # 4. Log metrics
        self._log_replan_metrics(strategy, success, new_task_ids)
        
        summary = f"{strategy.strategy_type.value}: {strategy.rationale}"
        return True, summary

    def _log_replan_metrics(
        self, 
        strategy: ReplanStrategy, 
        success: bool,
        new_task_ids: Optional[List[int]] = None
    ) -> None:
        """
        Log replan metrics for observability.
        
        Args:
            strategy: The replan strategy that was applied
            success: Whether the strategy application succeeded
            new_task_ids: List of new task IDs if decomposed/replaced
        """
        self.logger.info(
            "replan_metrics",
            strategy_type=strategy.strategy_type.value,
            confidence=strategy.confidence,
            success=success,
            new_task_ids=new_task_ids or [],
            modifications_count=len(strategy.modifications),
            rationale=strategy.rationale[:100]  # Truncate for logging
        )


    def _extract_failure_context(
        self,
        failed_item: TodoItem,
        error_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract structured failure context from a failed TodoItem.
        
        This method wraps the module-level extract_failure_context function
        and adds agent-specific context like available tools.
        
        Args:
            failed_item: The TodoItem that failed execution
            error_context: Optional additional error context
            
        Returns:
            Dictionary with failure context plus available tools list
        """
        # Use module-level extraction function
        context = extract_failure_context(failed_item, error_context)
        
        # Add available tools for LLM decision making
        context["available_tools"] = self._get_tools_description()
        
        return context


    async def generate_replan_strategy(
        self,
        failed_item: TodoItem,
        error_context: Optional[Dict[str, Any]] = None
    ) -> Optional[ReplanStrategy]:
        """Generate intelligent replan strategy from failure analysis.
        
        Uses LLM to analyze the failure and recommend one of three strategies:
        - RETRY_WITH_PARAMS: Adjust parameters and retry same tool
        - SWAP_TOOL: Use different tool to achieve same goal
        - DECOMPOSE_TASK: Split task into smaller subtasks
        
        Args:
            failed_item: The TodoItem that failed
            error_context: Optional additional error context (traceback, etc.)
            
        Returns:
            ReplanStrategy if generation succeeds and passes validation, None otherwise
        """
        self.logger.info(
            "generate_replan_strategy_start",
            task_position=failed_item.position,
            tool=failed_item.chosen_tool,
            attempts=failed_item.attempts
        )
        
        try:
            # Extract failure context
            context = self._extract_failure_context(failed_item, error_context)
            
            # Build LLM prompt
            prompt = REPLAN_PROMPT_TEMPLATE.format(**context)
            
            # Request strategy from LLM with timeout
            self.logger.debug("requesting_strategy_from_llm", prompt_length=len(prompt))
            
            response = await self.llm_service.complete(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=STRATEGY_GENERATION_TIMEOUT
            )
            
            # Parse LLM response
            if not response or not response.strip():
                self.logger.warning("llm_returned_empty_response")
                return None
            
            # Parse JSON response
            try:
                strategy_data = json.loads(response)
            except json.JSONDecodeError as e:
                self.logger.error("llm_response_not_json", error=str(e), response=response[:200])
                return None
            
            # Create strategy object
            try:
                strategy = ReplanStrategy.from_dict(strategy_data)
            except (ValueError, KeyError) as e:
                self.logger.error("invalid_strategy_structure", error=str(e), data=strategy_data)
                return None
            
            # Validate strategy
            if not validate_strategy(strategy, self.logger):
                self.logger.warning(
                    "strategy_validation_failed",
                    strategy_type=strategy.strategy_type.value,
                    confidence=strategy.confidence
                )
                return None
            
            self.logger.info(
                "replan_strategy_generated",
                strategy_type=strategy.strategy_type.value,
                confidence=strategy.confidence,
                rationale=strategy.rationale[:100]  # Truncate for logging
            )
            
            return strategy
            
        except Exception as e:
            self.logger.error(
                "generate_replan_strategy_failed",
                error=str(e),
                task_position=failed_item.position,
                exc_info=True
            )
            return None


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

    def _has_learning_pattern(self, step: TodoItem) -> bool:
        """
        Detect if TodoItem execution contains valuable learning patterns.
        
        Args:
            step: TodoItem to analyze
            
        Returns:
            True if learning pattern detected
        """
        # Pattern 1: Failed then succeeded (multiple attempts with eventual success)
        if step.status == TaskStatus.COMPLETED and step.attempts > 1:
            return True
        
        # Pattern 2: Replanning occurred (tried different approaches)
        if step.status == TaskStatus.COMPLETED and step.replan_count > 0:
            return True
        
        # Pattern 3: Tool substitution (changed tools during execution)
        if hasattr(step, 'execution_history') and len(step.execution_history) > 1:
            tools_used = [ex.get('tool') for ex in step.execution_history if ex.get('tool')]
            if len(set(tools_used)) > 1:  # Multiple different tools tried
                return True
        
        # Pattern 4: Error recovery (had errors but eventually succeeded)
        if step.execution_history:
            had_errors = any(ex.get('error') for ex in step.execution_history)
            if had_errors and step.status == TaskStatus.COMPLETED:
                return True
        
        return False

    async def _extract_lesson(self, step: TodoItem) -> Optional[Any]:
        """
        Extract lesson from execution history using LLM.
        
        Args:
            step: TodoItem with execution history
            
        Returns:
            SkillMemory object or None if extraction fails
        """
        try:
            from memory.memory_manager import SkillMemory
            
            # Build execution context
            context = self._build_execution_context(step)
            
            # Generate extraction prompt
            prompt = LESSON_EXTRACTION_PROMPT.format(**context)
            
            # Request lesson from LLM with timeout
            response = await asyncio.wait_for(
                self.llm_service.complete(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                ),
                timeout=5.0
            )
            
            lesson_data = json.loads(response)
            
            # Validate quality
            confidence = lesson_data.get("confidence", 0)
            if confidence < 0.7:
                self.logger.debug("Low confidence lesson, skipping", confidence=confidence)
                return None
            
            # Create SkillMemory
            memory = SkillMemory(
                context=lesson_data.get("context", ""),
                lesson=f"{lesson_data.get('what_failed', '')} → {lesson_data.get('what_worked', '')}. {lesson_data.get('lesson', '')}",
                tool_name=lesson_data.get("tool_name"),
                success_count=0,  # Will be incremented when used
            )
            
            return memory
            
        except asyncio.TimeoutError:
            self.logger.warning("Lesson extraction timed out")
            return None
        except Exception as e:
            self.logger.error("Lesson extraction failed", error=str(e))
            return None

    def _build_execution_context(self, step: TodoItem) -> Dict[str, Any]:
        """
        Build context dict for lesson extraction prompt.
        
        Args:
            step: TodoItem with execution history
            
        Returns:
            Context dictionary for prompt formatting
        """
        # Extract execution history details
        execution_history = []
        for idx, attempt in enumerate(step.execution_history, 1):
            execution_history.append({
                "attempt": idx,
                "tool": attempt.get("tool", "unknown"),
                "success": attempt.get("success", False),
                "error": attempt.get("error", "N/A")
            })
        
        # Get initial error (first failure)
        initial_error = "N/A"
        if step.execution_history:
            first_attempt = step.execution_history[0]
            if first_attempt.get("error"):
                initial_error = first_attempt["error"]
        
        # Get tools used
        tools_used = list(set(
            ex.get("tool", "unknown") 
            for ex in step.execution_history 
            if ex.get("tool")
        ))
        
        return {
            "task_description": step.description,
            "execution_history": json.dumps(execution_history, indent=2),
            "attempt_count": len(step.execution_history),
            "initial_error": initial_error,
            "final_result": str(step.execution_result),
            "tools_used": ", ".join(tools_used)
        }


    # create a static method to create an agent
    @staticmethod
    def create_agent(
        name: str,
        description: str,
        system_prompt: Optional[str],
        mission: Optional[str],
        work_dir: str,
        llm_service: LLMService,
        llm=None,
        tools: Optional[List[Tool]] = None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.PROMPT,
        enable_memory: bool = False,
        enable_lesson_extraction: bool = True
    ) -> "Agent":
        """
        Creates an agent with the given parameters.

        Args:
            name: The name of the agent.
            description: The description of the agent.
            system_prompt: The system prompt for the agent (defaults to GENERIC_SYSTEM_PROMPT if None).
            mission: The mission for the agent.
            work_dir: The work directory for the agent.
            llm_service: LLM service instance for the agent.
            llm: (Deprecated) Legacy LLM parameter for backward compatibility with LLMTool.
            tools: List of Tool instances to equip the agent with. If None, uses default tool set
                   (WebSearchTool, WebFetchTool, PythonTool, GitHubTool, GitTool, FileReadTool,
                   FileWriteTool, PowerShellTool, LLMTool).
            approval_policy: Policy for handling approval requests (default: PROMPT).
            enable_memory: Enable memory system for learned skills (default: False).
            enable_lesson_extraction: Enable automatic lesson extraction (default: True).

        Returns:
            An Agent instance with the specified configuration.
        """
        # Default to standard tool set if not provided (backward compatibility)
        if tools is None:
            tools = [
                WebSearchTool(),
                WebFetchTool(),
                PythonTool(),
                GitHubTool(),
                GitTool(),
                FileReadTool(),
                FileWriteTool(),
                PowerShellTool(),
                LLMTool(llm_service=llm_service),
            ]
        
        system_prompt = GENERIC_SYSTEM_PROMPT if system_prompt is None else system_prompt
        work_dir = Path(work_dir)
        work_dir.mkdir(exist_ok=True)

        # todolist directory is work_dir/todolists
        todolist_dir = work_dir / "todolists"
        todolist_dir.mkdir(exist_ok=True)
        planner = TodoListManager(base_dir=todolist_dir, llm_service=llm_service)

        # state directory is work_dir/states
        state_dir = work_dir / "states"
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(state_dir=state_dir)
        
        # memory directory is work_dir/memory (Story 4.1)
        memory_manager = None
        if enable_memory:
            from memory.memory_manager import MemoryManager
            memory_dir = work_dir / "memory"
            memory_dir.mkdir(exist_ok=True)
            memory_manager = MemoryManager(
                memory_dir=str(memory_dir),
                enable_memory=True,
                auto_prune=True,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )

        return Agent(name, description, system_prompt, mission, tools, planner, state_manager, llm_service, llm, approval_policy, memory_manager, enable_lesson_extraction)


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