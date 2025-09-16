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
# PLANNING COMPONENTS
# ============================================

class StepState(Enum):
    """States for plan steps"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    RETRY = "retry"

@dataclass
class PlanStep:
    """Single step in an execution plan"""
    id: str
    description: str
    tool: str
    parameters: Dict[str, Any]
    state: StepState = StepState.PENDING
    depends_on: List[str] = field(default_factory=list)
    required: bool = True
    max_retries: int = 3
    retry_count: int = 0
    
    # Execution details
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Planning metadata
    estimated_duration: Optional[int] = None  # seconds
    priority: int = 0  # Higher = more important
    can_parallel: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['state'] = self.state.value
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        """Create from dictionary"""
        data = data.copy()
        if 'state' in data:
            data['state'] = StepState(data['state'])
        if 'started_at' in data and data['started_at']:
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if 'completed_at' in data and data['completed_at']:
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)

@dataclass
class ExecutionPlan:
    """Complete execution plan with multiple steps"""
    id: str
    goal: str
    steps: List[PlanStep]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Plan metadata
    version: int = 1
    status: str = "active"  # active, completed, failed, replanning
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    
    # Context and memory
    context: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.total_steps = len(self.steps)
        self.update_stats()
    
    def update_stats(self):
        """Update plan statistics"""
        self.completed_steps = sum(1 for s in self.steps if s.state == StepState.COMPLETED)
        self.failed_steps = sum(1 for s in self.steps if s.state == StepState.FAILED)
        self.updated_at = datetime.now()
    
    def get_step_by_id(self, step_id: str) -> Optional[PlanStep]:
        """Get a specific step by ID"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def to_markdown(self) -> str:
        """Convert plan to markdown format"""
        md = f"# Execution Plan: {self.goal}\n\n"
        md += f"**ID:** {self.id}\n"
        md += f"**Created:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"**Updated:** {self.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"**Version:** {self.version}\n"
        md += f"**Status:** {self.status}\n\n"
        
        # Progress
        md += "## Progress\n\n"
        progress_pct = (self.completed_steps / self.total_steps * 100) if self.total_steps > 0 else 0
        md += f"- Total Steps: {self.total_steps}\n"
        md += f"- Completed: {self.completed_steps} ({progress_pct:.1f}%)\n"
        md += f"- Failed: {self.failed_steps}\n\n"
        
        # Steps
        md += "## Steps\n\n"
        for i, step in enumerate(self.steps, 1):
            # Status emoji
            status_icon = {
                StepState.PENDING: "⏳",
                StepState.IN_PROGRESS: "🔄",
                StepState.COMPLETED: "✅",
                StepState.FAILED: "❌",
                StepState.SKIPPED: "⏭️",
                StepState.BLOCKED: "🚫",
                StepState.RETRY: "🔁"
            }.get(step.state, "❓")
            
            md += f"### {i}. {status_icon} {step.description}\n\n"
            md += f"- **ID:** `{step.id}`\n"
            md += f"- **Tool:** `{step.tool}`\n"
            md += f"- **State:** {step.state.value}\n"
            md += f"- **Required:** {step.required}\n"
            
            if step.depends_on:
                md += f"- **Dependencies:** {', '.join(f'`{d}`' for d in step.depends_on)}\n"
            
            if step.parameters:
                md += f"- **Parameters:**\n```json\n{json.dumps(step.parameters, indent=2)}\n```\n"
            
            if step.error:
                md += f"- **Error:** {step.error}\n"
            
            if step.result and step.state == StepState.COMPLETED:
                result_str = json.dumps(step.result, indent=2)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "\n... (truncated)"
                md += f"- **Result:**\n```json\n{result_str}\n```\n"
            
            if step.started_at and step.completed_at:
                duration = (step.completed_at - step.started_at).total_seconds()
                md += f"- **Duration:** {duration:.2f} seconds\n"
            
            md += "\n"
        
        # Notes
        if self.notes:
            md += "## Notes\n\n"
            for note in self.notes:
                md += f"- {note}\n"
            md += "\n"
        
        return md
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "context": self.context,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionPlan':
        """Create from dictionary"""
        data = data.copy()
        data['steps'] = [PlanStep.from_dict(s) for s in data['steps']]
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

@dataclass
class ExecutionState:
    """State information for replanning"""
    completed_steps: List[Dict[str, Any]]
    failed_steps: List[Dict[str, Any]]
    current_context: Dict[str, Any]
    original_goal: str
    previous_plan_id: str
    version: int

class PlanManager:
    """
    Manages plan lifecycle: create, update, save, load, replan
    No execution logic - purely planning and state management
    """
    
    def __init__(self, model_client, model: str, available_tools: Dict[str, Any], save_dir: str = "./plans", *, verbose: bool = False, pretty: bool = True, redactor: Optional[Any] = None):
        self.client = model_client  # For LLM calls
        self.model = model
        self.available_tools = available_tools  # Tool registry for planning
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.verbose = verbose
        self.pretty = pretty
        # redactor: callable that takes an object and returns a redacted copy
        self._redactor = redactor
    
    async def create_plan(self, goal: str, context: Dict[str, Any] = None) -> ExecutionPlan:
        """Create a new execution plan"""
        
        tools_desc = "\n".join([
            f"- {name}: {tool.description}\n  parameters_schema: {json.dumps(tool.parameters_schema)}"
            for name, tool in self.available_tools.items()
        ])
        
        context_str = ""
        if context:
            context_str = f"\nContext available:\n{json.dumps(context, indent=2)}"
        
        prompt = f"""Create a detailed, step-by-step execution plan for this goal:
{goal}
{context_str}

Available tools:
{tools_desc}

Create a comprehensive plan with:
1. Clear, actionable steps
2. Proper dependencies between steps
3. Realistic parameter values
4. Error handling considerations

IMPORTANT:
- For each step, the 'parameters' MUST strictly follow the tool's parameters_schema above, including all 'required' fields.
- For the 'powershell' tool specifically:
  - Use valid PowerShell syntax (not bash). Examples: New-Item -ItemType Directory -Path "C:\\path"; Set-Content; Get-ChildItem
  - Always include a 'command' string that is executable under PowerShell
  - Provide a 'cwd' when file operations depend on a working directory (default repo root if unsure)

Return a JSON object with this structure:
{{
  "steps": [
    {{
      "id": "unique_step_id",
      "description": "Clear description of what this step does",
      "tool": "tool_name",
      "parameters": {{}},
      "depends_on": ["previous_step_id"],
      "required": true/false,
      "estimated_duration": seconds,
      "priority": 0-10,
      "can_parallel": false
    }}
  ],
  "notes": ["Any important considerations"]
}}
"""
        
        try:
            if self.verbose and self.pretty:
                logger.info(
                    "\n".join([
                        "==== LLM REQUEST: create_plan ====",
                        f"Model: {self.model}",
                        f"Temperature: 0.5",
                        "System:",
                        "\"\"\"",
                        "You are an expert execution planner. Create detailed, practical plans.",
                        "\"\"\"",
                        "User:",
                        "\"\"\"",
                        prompt,
                        "\"\"\"",
                    ])
                )
            elif self.verbose:
                log_payload = {
                    "endpoint": "chat.completions.create",
                    "phase": "create_plan:request",
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert execution planner. Create detailed, practical plans."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.5,
                }
                if self._redactor:
                    log_payload = self._redactor(log_payload)
                logger.info(json.dumps(log_payload, ensure_ascii=False))
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert execution planner. Create detailed, practical plans."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            raw_content = response.choices[0].message.content
            if self.verbose and self.pretty:
                logger.info(
                    "\n".join([
                        "==== LLM RESPONSE: create_plan ====",
                        "Content:",
                        "\"\"\"",
                        raw_content,
                        "\"\"\"",
                    ])
                )
            plan_data = json.loads(raw_content)
            if self.verbose and not self.pretty:
                log_response = {
                    "endpoint": "chat.completions.create",
                    "phase": "create_plan:response",
                    "content": plan_data,
                }
                if self._redactor:
                    log_response = self._redactor(log_response)
                logger.info(json.dumps(log_response, ensure_ascii=False))
            
            # Create plan steps
            steps = []
            for step_data in plan_data.get("steps", []):
                step = PlanStep(
                    id=step_data.get("id", str(uuid.uuid4())[:8]),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool", ""),
                    parameters=step_data.get("parameters", {}),
                    depends_on=step_data.get("depends_on", []),
                    required=step_data.get("required", True),
                    estimated_duration=step_data.get("estimated_duration"),
                    priority=step_data.get("priority", 0),
                    can_parallel=step_data.get("can_parallel", False)
                )
                steps.append(step)
            
            # Create execution plan
            plan = ExecutionPlan(
                id=str(uuid.uuid4())[:8],
                goal=goal,
                steps=steps,
                context=context or {},
                notes=plan_data.get("notes", [])
            )
            
            await self.save_plan(plan)
            
            logger.info(f"Created plan {plan.id} with {len(steps)} steps")
            if self.verbose:
                try:
                    logger.info("PLAN MARKDOWN BEGIN\n" + plan.to_markdown() + "\nPLAN MARKDOWN END")
                except Exception:
                    pass
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise
    
    async def replan(self, plan: ExecutionPlan, execution_state: ExecutionState) -> ExecutionPlan:
        """Create a new plan based on execution state"""
        
        logger.info(f"Replanning from plan {plan.id} v{plan.version}")
        
        prompt = f"""The current plan has encountered failures and needs adjustment.

Original goal: {execution_state.original_goal}

Completed steps:
{json.dumps(execution_state.completed_steps, indent=2)}

Failed steps with errors:
{json.dumps(execution_state.failed_steps, indent=2)}

Current context:
{json.dumps(execution_state.current_context, indent=2)}

Create a new plan that:
1. Works around the failures
2. Uses alternative approaches if needed
3. Leverages what has already been completed
4. Achieves the original goal

Return the same JSON structure as before."""
        
        try:
            if self.verbose and self.pretty:
                logger.info(
                    "\n".join([
                        "==== LLM REQUEST: replan ====",
                        f"Model: {self.model}",
                        f"Temperature: 0.7",
                        "System:",
                        "\"\"\"",
                        "You are an expert at adaptive planning and problem-solving.",
                        "\"\"\"",
                        "User:",
                        "\"\"\"",
                        prompt,
                        "\"\"\"",
                    ])
                )
            elif self.verbose:
                log_payload = {
                    "endpoint": "chat.completions.create",
                    "phase": "replan:request",
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert at adaptive planning and problem-solving."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                }
                if self._redactor:
                    log_payload = self._redactor(log_payload)
                logger.info(json.dumps(log_payload, ensure_ascii=False))
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at adaptive planning and problem-solving."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            raw_content = response.choices[0].message.content
            if self.verbose and self.pretty:
                logger.info(
                    "\n".join([
                        "==== LLM RESPONSE: replan ====",
                        "Content:",
                        "\"\"\"",
                        raw_content,
                        "\"\"\"",
                    ])
                )
            plan_data = json.loads(raw_content)
            if self.verbose:
                log_response = {
                    "endpoint": "chat.completions.create",
                    "phase": "replan:response",
                    "content": plan_data,
                }
                if self._redactor:
                    log_response = self._redactor(log_response)
                logger.info(json.dumps(log_response, ensure_ascii=False))
            
            # Create new plan steps
            new_steps = []
            
            # Keep completed steps
            for step in plan.steps:
                if step.state == StepState.COMPLETED:
                    new_steps.append(step)
            
            # Add new steps from replan
            for step_data in plan_data.get("steps", []):
                # Skip if this step was already completed
                if any(s.id == step_data.get("id") for s in new_steps):
                    continue
                
                step = PlanStep(
                    id=step_data.get("id", str(uuid.uuid4())[:8]),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool", ""),
                    parameters=step_data.get("parameters", {}),
                    depends_on=step_data.get("depends_on", []),
                    required=step_data.get("required", True),
                    estimated_duration=step_data.get("estimated_duration"),
                    priority=step_data.get("priority", 0),
                    can_parallel=step_data.get("can_parallel", False)
                )
                new_steps.append(step)
            
            # Create new plan version
            new_plan = ExecutionPlan(
                id=plan.id,  # Keep same ID
                goal=plan.goal,
                steps=new_steps,
                created_at=plan.created_at,
                version=plan.version + 1,
                context=execution_state.current_context,
                notes=plan.notes + [f"Replanned at v{plan.version + 1} due to failures"]
            )
            
            await self.save_plan(new_plan)
            
            logger.info(f"Created new plan version {new_plan.version} with {len(new_steps)} steps")
            if self.verbose:
                try:
                    logger.info("PLAN MARKDOWN BEGIN\n" + new_plan.to_markdown() + "\nPLAN MARKDOWN END")
                except Exception:
                    pass
            return new_plan
            
        except Exception as e:
            logger.error(f"Failed to replan: {e}")
            return plan
    
    def get_next_steps(self, plan: ExecutionPlan) -> List[PlanStep]:
        """Get next executable steps considering dependencies"""
        executable = []
        completed_ids = {s.id for s in plan.steps if s.state == StepState.COMPLETED}
        
        for step in plan.steps:
            if step.state != StepState.PENDING:
                continue
            
            # Check if all dependencies are completed
            deps_satisfied = all(dep in completed_ids for dep in step.depends_on)
            if deps_satisfied:
                executable.append(step)
        
        return executable
    
    def get_blocked_steps(self, plan: ExecutionPlan) -> List[PlanStep]:
        """Get steps blocked by failed dependencies"""
        failed_ids = {s.id for s in plan.steps if s.state == StepState.FAILED and s.required}
        blocked = []
        
        for step in plan.steps:
            if step.state == StepState.PENDING:
                if any(dep in failed_ids for dep in step.depends_on):
                    blocked.append(step)
        
        return blocked
    
    def update_step_state(self, plan: ExecutionPlan, step_id: str, 
                         state: StepState, result: Dict[str, Any] = None, 
                         error: str = None, started_at: datetime = None, 
                         completed_at: datetime = None):
        """Update a step's state after execution"""
        step = plan.get_step_by_id(step_id)
        if step:
            step.state = state
            if result is not None:
                step.result = result
            if error is not None:
                step.error = error
            if started_at is not None:
                step.started_at = started_at
            if completed_at is not None:
                step.completed_at = completed_at
            
            # Update plan statistics
            plan.update_stats()
    
    async def save_plan(self, plan: ExecutionPlan):
        """Save plan to file"""
        
        # Save as JSON
        json_path = self.save_dir / f"plan_{plan.id}_v{plan.version}.json"
        with open(json_path, 'w') as f:
            json.dump(plan.to_dict(), f, indent=2)
        
        # Save as Markdown
        md_path = self.save_dir / f"plan_{plan.id}_v{plan.version}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(plan.to_markdown())
        
        logger.debug(f"Saved plan to {json_path} and {md_path}")
    
    async def load_plan(self, plan_id: str, version: Optional[int] = None) -> Optional[ExecutionPlan]:
        """Load a plan from file"""
        
        if version:
            json_path = self.save_dir / f"plan_{plan_id}_v{version}.json"
        else:
            # Find latest version
            pattern = f"plan_{plan_id}_v*.json"
            files = list(self.save_dir.glob(pattern))
            if not files:
                return None
            json_path = max(files, key=lambda p: int(p.stem.split('_v')[-1]))
        
        if not json_path.exists():
            return None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        return ExecutionPlan.from_dict(data)


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
                "required": step.required,
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
                "If a tool is required, set use_tool with correct args",
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
        """Execute next steps of a persistent plan or create it once."""

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

        while plan.status == "active" and iterations < max_iterations:
            iterations += 1

            # Determine next step
            next_steps = self.plan_manager.get_next_steps(plan)
            step = next_steps[0] if next_steps else None
            if not step:
                plan.status = "completed" if self._all_steps_complete(plan) else "failed"
                break

            # Ask model for next action
            action = await self._decide_next_action(step, plan, mission, messages)

            if action.get("needs_user_input"):
                q = (action["needs_user_input"].get("question") or "").strip()
                await self.plan_manager.save_plan(plan)
                needs_user_input = True
                pending_question = q
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
                    completed_at=datetime.now(),
                )
                await self.plan_manager.save_plan(plan)
                continue

            if action.get("fail"):
                self.plan_manager.update_step_state(
                    plan,
                    step.id,
                    StepState.FAILED,
                    error=action["fail"].get("error", "Unknown failure"),
                    completed_at=datetime.now(),
                )
                await self.plan_manager.save_plan(plan)
                continue

            # Fallback: if action empty, mark failed to avoid loop
            self.plan_manager.update_step_state(
                plan,
                step.id,
                StepState.FAILED,
                error="No valid action returned",
                completed_at=datetime.now(),
            )
            await self.plan_manager.save_plan(plan)

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
        started_at = datetime.now()
        self.plan_manager.update_step_state(
            self.current_plan,
            step.id,
            StepState.IN_PROGRESS,
            started_at=started_at
        )

        # Execute with retry
        result = await self._execute_tool_with_retry(
            step.tool,
            step.parameters,
            task_id=step.id
        )

        completed_at = datetime.now()

        if result.success:
            # Update plan through manager
            self.plan_manager.update_step_state(
                self.current_plan,
                step.id,
                StepState.COMPLETED,
                result=result.result,
                completed_at=completed_at
            )

            # Store result in plan context
            self.current_plan.context[step.id] = result.result

            logger.info(f"Step {step.id} completed successfully")
            return True
        else:
            step.retry_count += 1

            if step.retry_count < step.max_retries:
                self.plan_manager.update_step_state(
                    self.current_plan,
                    step.id,
                    StepState.RETRY,
                    error=result.error,
                    completed_at=completed_at
                )
                logger.warning(f"Step {step.id} failed, will retry ({step.retry_count}/{step.max_retries})")
            else:
                self.plan_manager.update_step_state(
                    self.current_plan,
                    step.id,
                    StepState.FAILED,
                    error=result.error,
                    completed_at=completed_at
                )
                logger.error(f"Step {step.id} failed: {result.error}")

            return False

    def _all_steps_complete(self, plan: ExecutionPlan) -> bool:
        """Check if all steps are complete"""
        return all(
            step.state in [StepState.COMPLETED, StepState.SKIPPED]
            or (step.state == StepState.FAILED and not step.required)
            for step in plan.steps
        )

    def _should_replan(self, plan: ExecutionPlan) -> bool:
        """Determine if replanning is needed"""
        # Don't replan if we've already tried multiple times
        if plan.version > 3:
            return False

        # Replan if critical steps failed
        failed_required = sum(1 for s in plan.steps
                              if s.state == StepState.FAILED and s.required)

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
        started_at = datetime.now()
        self.plan_manager.update_step_state(plan, step.id, StepState.IN_PROGRESS, started_at=started_at)
        result = await self._execute_tool_with_retry(tool_name, args, task_id=step.id)
        completed_at = datetime.now()
        if result.success:
            self.plan_manager.update_step_state(
                plan, step.id, StepState.COMPLETED, result=result.result, completed_at=completed_at
            )
            plan.context[step.id] = result.result
            if self.config.verbose_logging:
                try:
                    logger.info(json.dumps({"tool": tool_name, "step": step.id, "phase": "result", "success": True, "result": result.result}, ensure_ascii=False))
                except Exception:
                    pass
            return True
        else:
            self.plan_manager.update_step_state(
                plan, step.id, StepState.FAILED, error=result.error, completed_at=completed_at
            )
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
                        result=result,
                        retries=attempt
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
                "required": s.required,
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
        prompt = f"""
        You are fixing parameters for the tool '{tool_name}'.
        The tool's expected parameters_schema is:
        {json.dumps(schema, indent=2)}

        The last execution failed with this error message:
        {error}

        Original parameters were:
        {json.dumps(parameters, indent=2)}

        Provide corrected parameters that strictly conform to the parameters_schema.
        Do not include any fields that are not in the schema. Return ONLY a valid JSON object.
        """

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

        system_prompt = """You are an AI assistant that uses tools to complete tasks.
Be efficient and combine operations when possible using the python tool.
Previous context may be available to help guide your decisions."""

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
                if step.started_at and step.completed_at:
                    duration = (step.completed_at - step.started_at).total_seconds()
                    print(f"  {step.description}: {duration:.2f}s")
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