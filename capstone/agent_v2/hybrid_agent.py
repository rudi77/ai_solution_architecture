"""
HybridAgent - Production-Ready AI Agent with Clean Architecture
Refactored with proper separation between Agent (execution) and PlanManager (planning)
"""

import os
import json
import asyncio
import subprocess
import inspect
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
import logging
import re
from collections import defaultdict
import urllib.request
import urllib.error
from enum import Enum
import uuid
import shutil

#from capstone.agent_v2.tool import Tool
from capstone.agent_v2.planning.planner import ExecutionPlan, ExecutionState, PlanManager, PlanStep, StepState
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool

# Optional imports
try:
    import aiohttp
except ImportError:
    aiohttp = None
    print("Warning: aiohttp not installed. Web tools will be limited.")

try:
    import openai
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIG & PROMPTS (policy)
# ============================================

@dataclass
class AgentConfig:
    """Lightweight agent configuration (policy, not transport)."""
    model: str = "gpt-4.1-mini"
    temperature: float = 0.7
    tool_profile: Optional[str] = None
    # Verbose diagnostics
    verbose_logging: bool = True
    pretty_logging: bool = True
    redact_sensitive: bool = True


class PromptLibrary:
    """Reusable system prompt builder."""

    @staticmethod
    def build_system_prompt(memory_ctx: str, config: 'AgentConfig') -> str:
        base = (
            "You are TaskForce Agent — a pragmatic, tool-using assistant for software and DevOps tasks.\n\n"
            "## Mission & Goals\n"
            "- Break goals into minimal, verifiable steps.\n"
            "- Prefer simple, deterministic actions that leave useful artifacts.\n\n"
            "## Tool Use Policy\n"
            "- Only call tools when necessary and with precise parameters.\n"
            "- Validate preconditions.\n"
            "- After each tool call: summarize briefly and plan the next step.\n\n"
            "## Output\n"
            "- Keep responses short and factual.\n\n"
            "## Safety\n"
            "- Never run destructive commands. Prefer idempotent operations.\n"
        )
        if memory_ctx:
            base += f"\nPrevious execution context:\n{memory_ctx}\n"
        return base

# ============================================
# STATE & PLANNING COMPONENTS
# ============================================

class AgentState(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"



# ============================================
# ORCHESTRATION COMPONENTS
# ============================================

@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    tool: str
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    retries: int = 0

@dataclass
class ExecutionMemory:
    """Stores execution history for context"""
    goal: str
    summary: str
    results: List[TaskResult]
    timestamp: datetime = field(default_factory=datetime.now)

# ============================================
# MAIN HYBRID AGENT
# ============================================

class HybridAgent:
    """
    Production-ready agent that executes plans and manages tools.
    Clean separation: Agent handles execution, PlanManager handles planning.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        max_retries: int = 3,
        enable_memory: bool = True,
        enable_planning: bool = True,
        plan_save_dir: str = "./plans",
        *,
        temperature: float = 0.7,
        tool_profile: Optional[str] = None,
        verbose_logging: Optional[bool] = None,
        redact_sensitive: Optional[bool] = None,
    ):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.enable_memory = enable_memory
        self.enable_planning = enable_planning
        self.temperature = float(temperature)
        # Determine verbosity/redaction from args or env
        env_verbose = os.getenv("AGENT_VERBOSE", "").lower() in ("1", "true", "yes", "on")
        env_redact = os.getenv("AGENT_REDACT", "").lower() not in ("0", "false", "no", "off")
        verbose_flag = env_verbose if verbose_logging is None else bool(verbose_logging)
        redact_flag = env_redact if redact_sensitive is None else bool(redact_sensitive)

        self.config = AgentConfig(
            model=self.model,
            temperature=self.temperature,
            tool_profile=tool_profile,
            verbose_logging=verbose_flag,
            redact_sensitive=redact_flag,
        )

        # Tool registry
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
        self._sync_class_tools()

        # Planning component (no circular reference)
        self.plan_manager = None
        if enable_planning:
            self.plan_manager = PlanManager(
                model_client=self.client,
                model=self.model,
                available_tools=self.tools,
                save_dir=plan_save_dir,
                verbose=self.config.verbose_logging,
                pretty=self.config.pretty_logging,
                redactor=(self._redact_payload if self.config.redact_sensitive else None),
            )

        # Current execution state
        self.current_plan: Optional[ExecutionPlan] = None

        # Execution context and memory
        self.context: Dict[str, Any] = {}
        self.memory: List[ExecutionMemory] = []
        self.max_memory_size = 10

        # Statistics
        self.stats = defaultdict(int)

    def bootstrap_turn(self, mission: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return initial system message and optional mission/user message."""
        system_prompt = PromptLibrary.build_system_prompt(self._get_memory_context(), self.config)
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if mission:
            msgs.append({"role": "user", "content": mission})
        return msgs

    # ---------------- Verbose diagnostics helpers ----------------
    def _redact_payload(self, obj: Any) -> Any:
        """Shallow redactor for sensitive fields in logs."""
        try:
            if isinstance(obj, dict):
                redacted = {}
                for k, v in obj.items():
                    key_lower = str(k).lower()
                    if key_lower in ("authorization", "api_key", "token", "password"):
                        redacted[k] = "***REDACTED***"
                    elif key_lower in ("messages", "content") and self.config.redact_sensitive is False:
                        redacted[k] = v
                    else:
                        redacted[k] = self._redact_payload(v)
                return redacted
            if isinstance(obj, list):
                return [self._redact_payload(i) for i in obj]
            return obj
        except Exception:
            return obj

    def _register_default_tools(self):
        """Register the default tool set"""
        default_tools = [
            # File operations
            FileReadTool(),
            FileWriteTool(),

            # Git operations
            GitTool(),

            # System operations
            #ShellTool(),
            PowerShellTool(),

            # Code execution
            PythonTool(),

            # Web operations
            WebSearchTool(),
            WebFetchTool(),

            # GitHub operations
            GitHubTool(),
        ]

        for tool in default_tools:
            self.register_tool(tool)


    def register_tool(self, tool: Tool):
        """Register a new tool"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    # -------- Class-level tool decorator and registry --------
    _tools: Dict[str, Tool] = {}

    @classmethod
    def tool(cls, name: str):
        def decorator(tool_class):
            instance = tool_class()
            # Prefer instance.name if available to avoid mismatch
            tool_name = getattr(instance, 'name', name)
            cls._tools[tool_name] = instance
            return tool_class
        return decorator

    def _sync_class_tools(self):
        """Merge class-level registered tools into instance registry once."""
        for name, tool in self.__class__._tools.items():
            if name not in self.tools:
                self.tools[name] = tool

    def get_tools_schema(self) -> List[Dict]:
        """Generate OpenAI function calling schema for all tools"""
        schemas = []
        for name, tool in self.tools.items():
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema
                }
            }
            schemas.append(schema)
        return schemas

    def _get_memory_context(self, limit: int = 3) -> str:
        """Get relevant memory context"""
        if not self.enable_memory or not self.memory:
            return ""

        recent_memory = self.memory[-limit:]
        context_parts = []

        for mem in recent_memory:
            success_rate = sum(1 for r in mem.results if r.success) / len(mem.results) * 100
            context_parts.append(
                f"Previous task: {mem.goal[:100]}\n"
                f"Summary: {mem.summary}\n"
                f"Success rate: {success_rate:.0f}%"
            )

        return "\n\n".join(context_parts)

    def get_memory_context(self, limit: int = 3) -> str:
        """Public accessor for external conversation orchestrators."""
        return self._get_memory_context(limit=limit)

    # -------- Minimal next-action decision helper --------
    async def _decide_next_action(
        self,
        step: 'PlanStep',
        plan: 'ExecutionPlan',
        mission: Optional[str],
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Ask the model for the next action in strict JSON."""
        tool_catalog = [
            {
                "name": name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
            }
            for name, tool in self.tools.items()
        ]

        system = (
            "You are a pragmatic task executor. Prefer the simplest valid action.\n"
            "Decide ONE action per turn, output STRICT JSON only."
        )

        user_payload = {
            "mission": mission,
            "plan": {
                "id": plan.id,
                "goal": plan.goal,
                "status": plan.status,
                "context": plan.context,
            },
            "current_step": {
                "id": step.id,
                "description": step.description,
                "tool": step.tool,
                "parameters": step.parameters,
                "depends_on": step.depends_on,
            },
            "messages": messages[-5:] if messages else [],
            "tools": tool_catalog,
            "response_schema": {
                "needs_user_input": {"question": "string"},
                "use_tool": {"name": "string", "args": {}},
                "mark_complete": {"result": {}, "notes": "string"},
                "fail": {"error": "string"},
            },
            "rules": [
                "If you need info from user, ONLY set needs_user_input.question",
                "If a tool is needed, set use_tool with correct args",
                "If no tool needed, set mark_complete",
                "Return VALID JSON only, no markdown",
            ],
        }

        try:
            if self.config.verbose_logging and self.plan_manager and getattr(self.plan_manager, "pretty", False):
                logger.info(
                    "\n".join([
                        "==== LLM REQUEST: decide_next_action ====",
                        f"Model: {self.model}",
                        f"Temperature: {self.temperature}",
                        "System:",
                        "\"\"\"",
                        system,
                        "\"\"\"",
                        "User:",
                        "\"\"\"",
                        json.dumps(user_payload),
                        "\"\"\"",
                    ])
                )
            elif self.config.verbose_logging:
                req_log = {
                    "endpoint": "chat.completions.create",
                    "phase": "decide_next_action:request",
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(user_payload)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": self.temperature,
                }
                payload = self._redact_payload(req_log) if self.config.redact_sensitive else req_log
                logger.info(json.dumps(payload, ensure_ascii=False))
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user_payload)},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
            )
            content = resp.choices[0].message.content
            if self.config.verbose_logging and self.plan_manager and getattr(self.plan_manager, "pretty", False):
                logger.info(
                    "\n".join([
                        "==== LLM RESPONSE: decide_next_action ====",
                        "Content:",
                        "\"\"\"",
                        content,
                        "\"\"\"",
                    ])
                )
            elif self.config.verbose_logging:
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = {"raw": content}
                res_log = {
                    "endpoint": "chat.completions.create",
                    "phase": "decide_next_action:response",
                    "content": parsed,
                }
                payload = self._redact_payload(res_log) if self.config.redact_sensitive else res_log
                logger.info(json.dumps(payload, ensure_ascii=False))
            return json.loads(content)
        except Exception as e:
            logger.error(f"Decision failed: {e}")
            return {"fail": {"error": str(e)}}

    # ------------- Planning path stays unchanged -------------
    async def execute(
        self,
        mission: Optional[str] = None,
        *,
        session_id: str,
        plan_id: Optional[str] = None,
        user_message: Optional[str] = None,
        max_iterations: int = 20
    ) -> Dict[str, Any]:
        """State-driven execution with explicit AgentState transitions."""

        # Ensure plan manager exists
        if not self.plan_manager:
            self.plan_manager = PlanManager(
                model_client=self.client,
                model=self.model,
                available_tools=self.tools,
                save_dir="./plans",
            )

        # Load or create plan
        plan = await self._get_or_create_plan(
            session_id=session_id,
            plan_id=plan_id,
            mission=mission,
            user_message=user_message,
        )
        self.current_plan = plan

        # Bootstrap minimal messages context
        messages: List[Dict[str, str]] = []
        if mission:
            messages.append({"role": "user", "content": mission})
        if user_message:
            messages.append({"role": "user", "content": user_message})

        iterations = 0
        needs_user_input = False
        pending_question: Optional[str] = None

        # Initialize state
        state = AgentState.EXECUTING if plan.steps else AgentState.PLANNING

        while plan.status == "active" and iterations < max_iterations:
            iterations += 1
            if state == AgentState.PLANNING:
                # Create a plan if none
                plan = await self._get_or_create_plan(
                    session_id=session_id,
                    plan_id=plan_id,
                    mission=mission,
                    user_message=user_message,
                )
                self.current_plan = plan
                state = AgentState.EXECUTING
                continue

            if state == AgentState.EXECUTING:
                next_steps = self.plan_manager.get_next_steps(plan)
                step = next_steps[0] if next_steps else None
                if not step:
                    plan.status = "completed" if self._all_steps_complete(plan) else "failed"
                    state = AgentState.COMPLETED if plan.status == "completed" else AgentState.FAILED
                    break

                action = await self._decide_next_action(step, plan, mission, messages)

                if action.get("needs_user_input"):
                    q = (action["needs_user_input"].get("question") or "").strip()
                    await self.plan_manager.save_plan(plan)
                    needs_user_input = True
                    pending_question = q
                    state = AgentState.WAITING_FOR_USER
                    break

                if action.get("use_tool"):
                    tool_name = action["use_tool"].get("name")
                    args = action["use_tool"].get("args", {})
                    await self._run_tool_into_step(step, tool_name, args, plan)
                    await self.plan_manager.save_plan(plan)
                    continue

                if action.get("mark_complete"):
                    self.plan_manager.update_step_state(
                        plan,
                        step.id,
                        StepState.COMPLETED,
                        result=action["mark_complete"].get("result"),
                    )
                    await self.plan_manager.save_plan(plan)
                    continue

                if action.get("fail"):
                    self.plan_manager.update_step_state(
                        plan,
                        step.id,
                        StepState.FAILED,
                        error=action["fail"].get("error", "Unknown failure"),
                    )
                    await self.plan_manager.save_plan(plan)
                    continue

                # Fallback: no valid action
                self.plan_manager.update_step_state(
                    plan,
                    step.id,
                    StepState.FAILED,
                    error="No valid action returned",
                )
                await self.plan_manager.save_plan(plan)
                continue

            if state == AgentState.WAITING_FOR_USER:
                # We exit loop returning needs_user_input; UI will resume later
                break

            if state in (AgentState.COMPLETED, AgentState.FAILED):
                break

        # Memory summary (optional)
        if self.enable_memory and self.current_plan:
            self._store_memory(self.current_plan.goal, [
                TaskResult(
                    task_id=s.id,
                    tool=s.tool,
                    success=s.state == StepState.COMPLETED,
                    result=s.result or {},
                    error=s.error,
                ) for s in self.current_plan.steps
            ])

        return {
            "success": plan.status == "completed",
            "plan_id": plan.id,
            "status": plan.status,
            "needs_user_input": needs_user_input,
            "question": pending_question,
            "completed_steps": plan.completed_steps,
            "failed_steps": plan.failed_steps,
            "total_steps": plan.total_steps,
            "messages": messages,
        }

    async def _get_or_create_plan(
        self,
        *,
        session_id: str,
        plan_id: Optional[str],
        mission: Optional[str],
        user_message: Optional[str],
    ) -> 'ExecutionPlan':
        """Load an existing plan or create a new one once per session."""
        if plan_id:
            loaded = await self.plan_manager.load_plan(plan_id)
            if loaded:
                return loaded
        # Create new plan
        context = {
            "session_id": session_id,
            "last_user_message": user_message,
        }
        plan = await self.plan_manager.create_plan(mission or "Untitled Mission", context=context)
        return plan

    async def _execute_step(self, step: PlanStep) -> bool:
        """Execute a single plan step - Agent's responsibility"""

        logger.info(f"Executing step {step.id}: {step.description}")

        # Update state
        self.plan_manager.update_step_state(
            self.current_plan,
            step.id,
            StepState.IN_PROGRESS
        )

        # Execute with retry
        result = await self._execute_tool_with_retry(
            step.tool,
            step.parameters,
            task_id=step.id
        )

        if result.success:
            # Update plan through manager
            self.plan_manager.update_step_state(
                self.current_plan,
                step.id,
                StepState.COMPLETED,
                result=result.result
            )

            # Store result in plan context
            self.current_plan.context[step.id] = result.result

            logger.info(f"Step {step.id} completed successfully")
            return True
        else:
            self.plan_manager.update_step_state(
                self.current_plan,
                step.id,
                StepState.FAILED,
                error=result.error
            )
            logger.error(f"Step {step.id} failed: {result.error}")
            return False

    def _all_steps_complete(self, plan: ExecutionPlan) -> bool:
        """Check if all steps are complete"""
        return all(step.state in [StepState.COMPLETED, StepState.SKIPPED] for step in plan.steps)

    def _should_replan(self, plan: ExecutionPlan) -> bool:
        """Determine if replanning is needed"""
        # Don't replan if we've already tried multiple times
        if plan.version > 3:
            return False

        # Replan if critical steps failed
        failed_required = sum(1 for s in plan.steps if s.state == StepState.FAILED)

        return failed_required > 0

    def _get_execution_state(self, plan: ExecutionPlan) -> ExecutionState:
        """Get current execution state for replanning"""

        completed_steps = [
            {"id": s.id, "description": s.description, "result": s.result}
            for s in plan.steps if s.state == StepState.COMPLETED
        ]

        failed_steps = [
            {"id": s.id, "description": s.description, "error": s.error}
            for s in plan.steps if s.state == StepState.FAILED
        ]

        return ExecutionState(
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            current_context=plan.context,
            original_goal=plan.goal,
            previous_plan_id=plan.id,
            version=plan.version
        )

    async def _run_tool_into_step(
        self,
        step: 'PlanStep',
        tool_name: str,
        args: Dict[str, Any],
        plan: 'ExecutionPlan',
    ) -> bool:
        """Execute a tool and write state/contexts into the step/plan."""
        logger.info(f"Executing tool {tool_name} for step {step.id}")
        if self.config.verbose_logging:
            try:
                log_args = self._redact_payload(args) if self.config.redact_sensitive else args
                logger.info(json.dumps({"tool": tool_name, "step": step.id, "phase": "invoke", "args": log_args}, ensure_ascii=False))
            except Exception:
                pass
        self.plan_manager.update_step_state(plan, step.id, StepState.IN_PROGRESS)
        result = await self._execute_tool_with_retry(tool_name, args, task_id=step.id)
        if result.success:
            self.plan_manager.update_step_state(
                plan, step.id, StepState.COMPLETED, result=result.result
            )
            plan.context[step.id] = result.result
            if self.config.verbose_logging:
                try:
                    logger.info(json.dumps({"tool": tool_name, "step": step.id, "phase": "result", "success": True, "result": result.result}, ensure_ascii=False))
                except Exception:
                    pass
            return True
        else:
            self.plan_manager.update_step_state(plan, step.id, StepState.FAILED, error=result.error)
            if self.config.verbose_logging:
                try:
                    logger.info(json.dumps({"tool": tool_name, "step": step.id, "phase": "result", "success": False, "error": result.error}, ensure_ascii=False))
                except Exception:
                    pass
            return False

    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        task_id: str = None
    ) -> TaskResult:
        """Execute a tool with retry logic"""
        tool = self.tools.get(tool_name)
        if not tool:
            return TaskResult(
                task_id=task_id or f"task_{datetime.now().timestamp()}",
                tool=tool_name,
                success=False,
                result={},
                error=f"Tool '{tool_name}' not found"
            )

        # Validate parameters
        valid, error = tool.validate_params(**parameters)
        if not valid:
            return TaskResult(
                task_id=task_id or f"task_{datetime.now().timestamp()}",
                tool=tool_name,
                success=False,
                result={},
                error=error
            )

        # Try execution with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Add context for Python tool
                if tool_name == "python":
                    parameters["context"] = self.context

                # Execute tool
                if self.config.verbose_logging:
                    try:
                        log_params = self._redact_payload(parameters) if self.config.redact_sensitive else parameters
                        logger.info(json.dumps({"tool": tool_name, "phase": "attempt", "attempt": attempt + 1, "params": log_params}, ensure_ascii=False))
                    except Exception:
                        pass
                result = await tool.execute(**parameters)

                # Update statistics
                self.stats[f"{tool_name}_calls"] += 1

                if result.get("success"):
                    self.stats[f"{tool_name}_success"] += 1
                    if self.config.verbose_logging:
                        try:
                            logger.info(json.dumps({"tool": tool_name, "phase": "attempt_result", "attempt": attempt + 1, "success": True, "result": result}, ensure_ascii=False))
                        except Exception:
                            pass
                    return TaskResult(
                        task_id=task_id or f"task_{datetime.now().timestamp()}",
                        tool=tool_name,
                        success=True,
                        result=result
                    )

                # Derive a clearer error message when available
                last_error = result.get("error") or result.get("stderr") or (
                    f"Return code {result.get('returncode')}" if result.get("returncode") not in (None, 0) else "Unknown error"
                )

                # Try to fix parameters if we have more attempts
                if attempt < self.max_retries - 1:
                    fixed_params = await self._fix_parameters(
                        tool_name, parameters, last_error
                    )
                    if fixed_params:
                        parameters.update(fixed_params)
                        logger.info(f"Retrying {tool_name} with fixed parameters")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Tool execution failed: {e}")

        self.stats[f"{tool_name}_failures"] += 1
        if self.config.verbose_logging:
            try:
                logger.info(json.dumps({"tool": tool_name, "phase": "final_failure", "error": last_error}, ensure_ascii=False))
            except Exception:
                pass
        return TaskResult(
            task_id=task_id or f"task_{datetime.now().timestamp()}",
            tool=tool_name,
            success=False,
            result={},
            error=last_error,
            retries=self.max_retries
        )

    # ---------------- Introspection helpers for tasks/plan ----------------
    def get_task_list(self) -> List[Dict[str, Any]]:
        """Return a concise view of current plan steps (task list)."""
        plan = self.current_plan
        if not plan:
            return []
        tasks = []
        for s in plan.steps:
            tasks.append({
                "id": s.id,
                "description": s.description,
                "tool": s.tool,
                "state": s.state.value,
                "depends_on": s.depends_on,
                "parameters": s.parameters,
            })
        if self.config.verbose_logging:
            try:
                logger.info(json.dumps({"phase": "task_list", "tasks": tasks}, ensure_ascii=False))
            except Exception:
                pass
        return tasks

    def get_plan_markdown(self) -> Optional[str]:
        """Return the current plan as markdown."""
        plan = self.current_plan
        if not plan:
            return None
        md = plan.to_markdown()
        if self.config.verbose_logging:
            try:
                logger.info("PLAN MARKDOWN BEGIN\n" + md + "\nPLAN MARKDOWN END")
            except Exception:
                pass
        return md

    async def _fix_parameters(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        error: str
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to fix parameters based on error. Include tool schema for guidance."""
        tool = self.tools.get(tool_name)
        schema = tool.parameters_schema if tool else {}
        prompt = (
            "You are fixing parameters for the tool '" + tool_name + "'.\n"
            "The tool's expected parameters_schema is:\n" + json.dumps(schema, indent=2) + "\n\n"
            "The last execution failed with this error message:\n" + str(error) + "\n\n"
            "Original parameters were:\n" + json.dumps(parameters, indent=2) + "\n\n"
            "Provide corrected parameters that strictly conform to the parameters_schema.\n"
            "Do not include any fields that are not in the schema. Return ONLY a valid JSON object."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a debugging assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Failed to fix parameters: {e}")
            return None

    # -------- Back-compat path (builds messages then delegates) --------
    async def execute_with_function_calling(
        self,
        goal: str,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """Execute goal using OpenAI function calling for tool selection (compat wrapper)."""

        # Initialize conversation with memory context
        memory_context = self._get_memory_context()

        system_prompt = (
            "You are an AI assistant that uses tools to complete tasks.\n"
            "Be efficient and combine operations when possible using the python tool.\n"
            "Previous context may be available to help guide your decisions."
        )

        if memory_context:
            system_prompt += f"\n\nPrevious execution context:\n{memory_context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": goal}
        ]

        result = await self.run_messages(messages, max_iterations=max_iterations)

        # For BC: shape the classic return payload
        results = result.get("results", [])
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": result.get("success", False),
            "goal": goal,
            "results": [
                {
                    "task_id": r["task_id"],
                    "tool": r["tool"],
                    "success": r["success"],
                    "error": r["error"],
                    "retries": r["retries"]
                }
                for r in results
            ],
            "summary": f"Executed {len(results)} tasks, {success_count} successful",
            "context": self.context,
            "iterations": result.get("iterations", 0),
            "stats": dict(self.stats),
            "needs_user_input": result.get("needs_user_input", False),
            "question": result.get("question"),
            "messages": result.get("messages"),
        }

    async def resume_plan(self, plan_id: str, version: Optional[int] = None, messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Resume execution of an existing plan"""

        if not self.plan_manager:
            return {"success": False, "error": "Planning not enabled"}

        # Load plan
        plan = await self.plan_manager.load_plan(plan_id, version)
        if not plan:
            return {"success": False, "error": f"Plan {plan_id} not found"}

        logger.info(f"Resuming plan {plan_id} v{plan.version}")
        self.current_plan = plan

        # Determine session and optional last user message
        session_id = str(plan.context.get("session_id", plan.id))
        last_user_message: Optional[str] = None
        if messages:
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "user":
                    last_user_message = m.get("content")
                    break

        # Continue execution from current state using new signature
        return await self.execute(
            plan.goal,
            session_id=session_id,
            plan_id=plan.id,
            user_message=last_user_message,
        )

    def _store_memory(self, goal: str, results: List[TaskResult]):
        """Store execution in memory"""
        summary = f"Completed {len(results)} tasks, " \
                  f"{sum(1 for r in results if r.success)} successful"

        memory_entry = ExecutionMemory(
            goal=goal[:200],  # Truncate long goals
            summary=summary,
            results=results
        )

        self.memory.append(memory_entry)

        # Limit memory size
        if len(self.memory) > self.max_memory_size:
            self.memory.pop(0)

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total_calls = sum(v for k, v in self.stats.items() if k.endswith("_calls"))
        total_success = sum(v for k, v in self.stats.items() if k.endswith("_success"))

        tool_stats = {}
        for tool_name in self.tools.keys():
            calls = self.stats.get(f"{tool_name}_calls", 0)
            success = self.stats.get(f"{tool_name}_success", 0)
            failures = self.stats.get(f"{tool_name}_failures", 0)

            if calls > 0:
                tool_stats[tool_name] = {
                    "calls": calls,
                    "success": success,
                    "failures": failures,
                    "success_rate": (success / calls) * 100
                }

        return {
            "total_calls": total_calls,
            "total_success": total_success,
            "overall_success_rate": (total_success / total_calls * 100) if total_calls > 0 else 0,
            "tools": tool_stats,
            "memory_entries": len(self.memory),
            "current_plan": self.current_plan.id if self.current_plan else None
        }

    def clear_context(self):
        """Clear execution context"""
        self.context.clear()
        logger.info("Context cleared")

    def clear_memory(self):
        """Clear execution memory"""
        self.memory.clear()
        logger.info("Memory cleared")


# ============================================
# CUSTOM TOOL EXAMPLE
# ============================================

class DatabaseTool(Tool):
    """Custom tool for database operations"""
    
    @property
    def name(self) -> str:
        return "database"
    
    @property
    def description(self) -> str:
        return "Execute database operations (SQLite)"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create_table", "insert", "select", "update", "delete"],
                    "description": "Database operation to perform"
                },
                "query": {
                    "type": "string",
                    "description": "SQL query to execute"
                },
                "db_path": {
                    "type": "string",
                    "description": "Path to database file"
                },
                "values": {
                    "type": "array",
                    "description": "Values for parameterized queries"
                }
            },
            "required": ["operation"]
        }
    
    async def execute(self, operation: str, query: str = None, db_path: str = "data.db", **kwargs) -> Dict[str, Any]:
        import sqlite3
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if operation == "create_table":
                cursor.execute(query)
                conn.commit()
                return {"success": True, "message": "Table created"}
            
            elif operation == "insert":
                cursor.execute(query, kwargs.get("values", ()))
                conn.commit()
                return {"success": True, "rows_affected": cursor.rowcount}
            
            elif operation == "select":
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "count": len(rows)
                }
            
            elif operation == "update":
                cursor.execute(query, kwargs.get("values", ()))
                conn.commit()
                return {"success": True, "rows_affected": cursor.rowcount}
            
            elif operation == "delete":
                cursor.execute(query, kwargs.get("values", ()))
                conn.commit()
                return {"success": True, "rows_affected": cursor.rowcount}
            
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

# ============================================
# USAGE EXAMPLES
# ============================================

async def main():
    """Example usage of the refactored HybridAgent"""
    api_key = os.getenv("OPENAI_API_KEY")
    # Initialize agent with planning enabled
    agent = HybridAgent(
        api_key=api_key,
        model="gpt-4.1",
        enable_planning=True,
        plan_save_dir="./execution_plans",
        verbose_logging=True,
        redact_sensitive=True
    )
    
    # Example 1: Create and deploy a web application
    goal1 = """
    Create a new fastapi project called "payment-api" with the following features:
    1. Create the project directory structure
    2. Set up a FastAPI application with proper structure (routers, models, services)
    3. Add health check and basic CRUD endpoints
    4. Create requirements.txt with necessary dependencies
    5. Add a comprehensive README.md
    6. Initialize git repository
    7. Create GitHub repository (if gh CLI is available)
    8. Create initial commit
    9. Push the code to the GitHub repository
    """
    
    print("=" * 60)
    print("Example 1: Web Application Development")
    print("=" * 60)
    
    result = await agent.execute(goal1, session_id="example1")
    
    print(f"Success: {result['success']}")
    print(f"Plan ID: {result.get('plan_id')}")
    print(f"Completed: {result.get('completed_steps')}/{result.get('total_steps')} steps")
    print(f"Plan saved to: {result.get('plan_file')}")
    
    # Example 2: Data analysis with dynamic replanning
#    " goal2 = """
#     Analyze CSV files in the 'data' directory:
#     1. Read all CSV files
#     2. Generate summary statistics
#     3. Create visualizations
#     4. Write a comprehensive report
#     """
    
#     print("\n" + "=" * 60)
#     print("Example 2: Data Analysis Pipeline")
#     print("=" * 60)
    
#     result = await agent.execute(goal2, session_id="example2")
    
#     print(f"Success: {result['success']}")
#     print(f"Status: {result.get('status')}")
    
#     # Example 3: Resume a previous plan
#     if result.get('plan_id'):
#         print("\n" + "=" * 60)
#         print("Example 3: Resuming Previous Plan")
#         print("=" * 60)
        
#         resume_result = await agent.resume_plan(result['plan_id'])
#         print(f"Resume Success: {resume_result['success']}")
    
#     # Example 4: Direct execution without planning
#     print("\n" + "=" * 60)
#     print("Example 4: Direct Execution with Function Calling")
#     print("=" * 60)
    
#     result = await agent.execute(
#         "Create a Python script that generates random passwords",
#         session_id="example4"
#     )
    
#     print(f"Success: {result['success']}")
#     print(f"Tasks executed: {len(result['results'])}")
#     print(f"Summary: {result['summary']}")
    
#     # Get execution statistics
#     print("\n" + "=" * 60)
#     print("Execution Statistics")
#     print("=" * 60)
    
#     stats = agent.get_statistics()
#     print(f"Total tool calls: {stats['total_calls']}")
#     print(f"Success rate: {stats['overall_success_rate']:.1f}%")
#     print(f"Memory entries: {stats['memory_entries']}")
    
#     if stats['tools']:
#         print("\nTool usage:")
#         for tool, tool_stats in stats['tools'].items():
#             print(f"  {tool}:")
#             print(f"    Calls: {tool_stats['calls']}")
#             print(f"    Success rate: {tool_stats['success_rate']:.1f}%")"

async def advanced_example():
    """Advanced example with custom tools and complex planning"""
    
    # Initialize agent
    agent = HybridAgent(
        api_key="your-openai-api-key",
        model="gpt-4",
        enable_planning=True
    )
    
    # Register custom database tool
    agent.register_tool(DatabaseTool())
    
    # Complex goal requiring multiple tools and replanning
    goal = """
    Build a complete data pipeline:
    1. Create SQLite database with tables for users and transactions
    2. Generate synthetic test data (1000 users, 5000 transactions)
    3. Analyze the data and create summary statistics
    4. Generate visualizations and save as images
    5. Create a markdown report with all findings
    6. Initialize Git repo and commit everything
    7. Create GitHub repository and push
    """
    
    print("Executing complex data pipeline...")
    result = await agent.execute_with_planning(goal)
    
    if result['success']:
        print("Pipeline completed successfully!")
        print(f"View the plan at: {result['plan_file']}")
        
        # Access the plan directly
        plan = agent.current_plan
        if plan:
            # Print execution timeline
            print("\nExecution Timeline:")
            for step in plan.steps:
                print(f"  {step.description}: {step.state.value}")
    else:
        print(f"Pipeline failed: {result.get('status')}")
        print(f"Failed steps: {result.get('failed_steps')}")

async def test_replanning():
    """Test the replanning capability"""
    
    agent = HybridAgent(
        api_key="your-openai-api-key",
        model="gpt-4",
        enable_planning=True
    )
    
    # Goal that might require replanning
    goal = """
    Deploy a web service:
    1. Create a FastAPI application
    2. Write unit tests
    3. Run tests (this might fail initially)
    4. Fix any issues and rerun tests
    5. Create Docker container
    6. Push to Docker Hub
    """
    
    print("Testing replanning capability...")
    result = await agent.execute_with_planning(goal)
    
    print(f"Final status: {result['status']}")
    print(f"Plan version: {agent.current_plan.version if agent.current_plan else 'N/A'}")
    
    if agent.current_plan and agent.current_plan.version > 1:
        print(f"Plan was replanned {agent.current_plan.version - 1} times")

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    import sys
    
    # Check for API key
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Please provide OpenAI API key as argument or set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Run examples
    print("Running HybridAgent Examples...")
    print("=" * 60)
    
    # Basic example
    asyncio.run(main())
    
    # Advanced example with custom tools
    # asyncio.run(advanced_example())
    
    # Test replanning
    # asyncio.run(test_replanning())