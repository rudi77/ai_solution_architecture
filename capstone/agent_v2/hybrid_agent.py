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
    
    def __init__(self, model_client, model: str, available_tools: Dict[str, Any], save_dir: str = "./plans"):
        self.client = model_client  # For LLM calls
        self.model = model
        self.available_tools = available_tools  # Tool registry for planning
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
    
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
- For the 'powershell' tool specifically, 'parameters' MUST include a 'command' string with a valid PowerShell command.

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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert execution planner. Create detailed, practical plans."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at adaptive planning and problem-solving."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            
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
# BASE TOOL INTERFACE
# ============================================

class Tool(ABC):
    """Base class for all tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Override to provide custom parameter schema for OpenAI function calling"""
        return self._generate_schema_from_signature()
    
    def _generate_schema_from_signature(self) -> Dict[str, Any]:
        """Auto-generate parameter schema from execute method signature"""
        sig = inspect.signature(self.execute)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            # Determine parameter type
            param_type = "string"  # Default
            param_desc = f"Parameter {param_name}"
            
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == Dict or param.annotation == dict:
                    param_type = "object"
                elif param.annotation == List or param.annotation == list:
                    param_type = "array"
            
            properties[param_name] = {
                "type": param_type,
                "description": param_desc
            }
            
            # Check if required
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
    
    def validate_params(self, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate parameters before execution"""
        sig = inspect.signature(self.execute)
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            if param.default == inspect.Parameter.empty and param_name not in kwargs:
                return False, f"Missing required parameter: {param_name}"
        
        return True, None

# ============================================
# FILE SYSTEM TOOLS
# ============================================

class FileReadTool(Tool):
    """Safe file reading with size limits"""
    
    @property
    def name(self) -> str:
        return "file_read"
    
    @property
    def description(self) -> str:
        return "Read file contents safely with size limits and encoding detection"
    
    async def execute(self, path: str, encoding: str = "utf-8", max_size_mb: int = 10, **kwargs) -> Dict[str, Any]:
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {"success": False, "error": f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB"}
            
            content = file_path.read_text(encoding=encoding)
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": str(file_path.absolute())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class FileWriteTool(Tool):
    """Safe file writing with backup option"""
    
    @property
    def name(self) -> str:
        return "file_write"
    
    @property
    def description(self) -> str:
        return "Write content to file with backup and safety checks"
    
    async def execute(self, path: str, content: str, backup: bool = True, **kwargs) -> Dict[str, Any]:
        try:
            file_path = Path(path)
            
            # Backup existing file
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text(), encoding='utf-8')
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            file_path.write_text(content, encoding='utf-8')
            
            return {
                "success": True,
                "path": str(file_path.absolute()),
                "size": len(content),
                "backed_up": backup and file_path.exists()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# GIT TOOL
# ============================================

class GitTool(Tool):
    """Comprehensive Git operations"""
    
    @property
    def name(self) -> str:
        return "git"
    
    @property
    def description(self) -> str:
        return "Execute git operations (init, add, commit, push, status, clone, etc.)"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["init", "add", "commit", "push", "status", "clone", "remote"],
                    "description": "Git operation to perform"
                },
                "repo_path": {
                    "type": "string",
                    "description": "Repository path (default: current directory)"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (for commit operation)"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to add (for add operation)"
                },
                "url": {
                    "type": "string",
                    "description": "Remote URL (for remote/clone operations)"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name"
                }
            },
            "required": ["operation"]
        }
    
    async def execute(self, operation: str, repo_path: str = ".", **kwargs) -> Dict[str, Any]:
        try:
            repo_path = Path(repo_path)
            
            # Build command based on operation
            if operation == "init":
                cmd = ["git", "init", "-b", kwargs.get("branch", "main")]
            elif operation == "add":
                files = kwargs.get("files", ["."])
                cmd = ["git", "add"] + files
            elif operation == "commit":
                message = kwargs.get("message", "Commit via HybridAgent")
                cmd = ["git", "commit", "-m", message]
            elif operation == "push":
                remote = kwargs.get("remote", "origin")
                branch = kwargs.get("branch", "main")
                cmd = ["git", "push", "-u", remote, branch]
            elif operation == "status":
                cmd = ["git", "status", "--short"]
            elif operation == "clone":
                url = kwargs.get("url")
                if not url:
                    return {"success": False, "error": "URL required for clone"}
                cmd = ["git", "clone", url, str(repo_path)]
            elif operation == "remote":
                action = kwargs.get("action", "add")
                if action == "add":
                    cmd = ["git", "remote", "add", kwargs.get("name", "origin"), kwargs["url"]]
                else:
                    cmd = ["git", "remote", "-v"]
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            # Execute command
            result = subprocess.run(
                cmd,
                cwd=repo_path if operation != "clone" else ".",
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "command": " ".join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# SHELL TOOL
# ============================================

class ShellTool(Tool):
    """Execute shell commands with safety limits"""
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute shell commands with timeout and safety limits"
    
    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict[str, Any]:
        try:
            # Safety check - block dangerous commands
            dangerous_patterns = [
                "rm -rf /", "rm -rf /*", 
                "dd if=/dev/zero", "dd if=/dev/random",
                "format c:", "del /f /s /q",
                ":(){ :|:& };:",  # Fork bomb
                "> /dev/sda",
                "mkfs.",
            ]
            
            if any(pattern in command.lower() for pattern in dangerous_patterns):
                return {"success": False, "error": "Command blocked for safety reasons"}
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": process.returncode,
                    "command": command
                }
            except asyncio.TimeoutError:
                process.kill()
                return {"success": False, "error": f"Command timed out after {timeout}s"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# Power Shell Tool
# ============================================

class PowerShellTool(Tool):
    """Execute PowerShell commands with safety limits"""
    
    @property
    def name(self) -> str:
        return "powershell"
    
    @property
    def description(self) -> str:
        return "Execute PowerShell commands with timeout and safety limits"

    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict[str, Any]:

        # Safety check - block dangerous powershell commands (case-insensitive)
        dangerous_patterns = [
            "Remove-Item -Path * -Force",
            "Remove-Item -Path * -Recurse",
            "Remove-Item -Path * -Recurse -Force",
            "Remove-Item -Path * -Recurse -Force",
        ]
        lower_cmd = command.lower()
        lower_patterns = [p.lower() for p in dangerous_patterns]
        if any(pattern in lower_cmd for pattern in lower_patterns):
            return {"success": False, "error": "Command blocked for safety reasons"}

        # Resolve PowerShell executable
        shell_exe = shutil.which("pwsh") or shutil.which("powershell")
        if not shell_exe:
            return {"success": False, "error": "No PowerShell executable found (pwsh/powershell)"}

        try:
            # Execute command explicitly via PowerShell
            process = await asyncio.create_subprocess_exec(
                shell_exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else "",
            "returncode": process.returncode,
            "command": command
        }


# ============================================
# PYTHON CODE EXECUTION TOOL
# ============================================

class PythonTool(Tool):
    """Execute Python code for complex operations"""
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def description(self) -> str:
        return "Execute Python code for complex logic, data processing, and custom operations. Code should set 'result' variable."
    
    async def execute(self, code: str, context: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute Python code in controlled namespace.
        Code has access to standard libraries and must set 'result' variable.
        """
        
        # Create safe namespace
        safe_namespace = {
            "__builtins__": {
                # Basic functions
                "print": print, "len": len, "range": range, "enumerate": enumerate,
                "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "sum": sum, "min": min, "max": max, "abs": abs,
                "round": round, "sorted": sorted, "reversed": reversed,
                "zip": zip, "map": map, "filter": filter,
                "any": any, "all": all, "isinstance": isinstance,
                "open": open,  # Use with caution
                "__import__": __import__,
            },
            "context": context or {},
        }
        
        # Import common libraries
        import_code = """
import os, sys, json, re, pathlib, shutil
import subprocess, datetime, time, random
import base64, hashlib, tempfile, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
"""
        
        try:
            # Execute imports
            exec(import_code, safe_namespace)
            
            # Execute user code
            exec(code, safe_namespace)
            
            # Extract result
            result_value = safe_namespace.get('result', None)
            
            # Get all user-defined variables
            user_vars = {
                k: v for k, v in safe_namespace.items()
                if not k.startswith('_') 
                and k not in ['os', 'sys', 'json', 're', 'pathlib', 'shutil',
                             'subprocess', 'datetime', 'time', 'random',
                             'base64', 'hashlib', 'tempfile', 'csv', 'Path',
                             'timedelta', 'Dict', 'List', 'Any', 'Optional', 'context']
            }
            
            return {
                "success": True,
                "result": result_value,
                "variables": user_vars,
                "context_updated": safe_namespace.get('context', {})
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }

# ============================================
# WEB TOOLS
# ============================================

class WebSearchTool(Tool):
    """Web search using DuckDuckGo (no API key required)"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo"
    
    async def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                }
                
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    results = []
                    
                    # Extract abstract if available
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "snippet": data["Abstract"],
                            "url": data.get("AbstractURL", "")
                        })
                    
                    # Extract related topics
                    for topic in data.get("RelatedTopics", [])[:num_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0][:50],
                                "snippet": topic.get("Text", ""),
                                "url": topic.get("FirstURL", "")
                            })
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": results[:num_results],
                        "count": len(results)
                    }
                    
        except Exception as e:
            return {"success": False, "error": str(e)}

class WebFetchTool(Tool):
    """Fetch content from URLs"""
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch and extract content from a URL"
    
    async def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    content = await response.text()
                    
                    # Simple HTML extraction
                    if "text/html" in response.headers.get("Content-Type", ""):
                        # Remove HTML tags (basic)
                        text = re.sub('<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                        text = re.sub('<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                        text = re.sub('<[^>]+>', '', text)
                        text = ' '.join(text.split())[:5000]  # Limit size
                    else:
                        text = content[:5000]
                    
                    return {
                        "success": True,
                        "url": url,
                        "status": response.status,
                        "content": text,
                        "content_type": response.headers.get("Content-Type", ""),
                        "length": len(content)
                    }
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# GITHUB TOOL
# ============================================

class GitHubTool(Tool):
    """GitHub operations using GitHub REST API (requires GITHUB_TOKEN)"""
    
    @property
    def name(self) -> str:
        return "github"
    
    @property
    def description(self) -> str:
        return "GitHub operations (create/list/delete repos) using REST API. Requires GITHUB_TOKEN."
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_repo", "list_repos", "delete_repo"],
                    "description": "GitHub action to perform"
                },
                "name": {
                    "type": "string",
                    "description": "Repository name"
                },
                "private": {
                    "type": "boolean",
                    "description": "Make repository private"
                },
                "description": {
                    "type": "string",
                    "description": "Repository description"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        try:
            token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
            if not token:
                return {"success": False, "error": "GITHUB_TOKEN environment variable is not set"}
            
            api_base = "https://api.github.com"
            
            def request(method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, str]:
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "HybridAgent"
                }
                data_bytes = None
                if body is not None:
                    data_bytes = json.dumps(body).encode("utf-8")
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.getcode(), resp.read().decode("utf-8")
            
            if action == "create_repo":
                repo_name = kwargs.get("name")
                if not repo_name:
                    return {"success": False, "error": "Repository name required"}
                body = {
                    "name": repo_name,
                    "private": bool(kwargs.get("private", False)),
                    "description": kwargs.get("description") or ""
                }
                status, text = request("POST", f"{api_base}/user/repos", body)
                ok = status in (200, 201)
                payload = {}
                try:
                    payload = json.loads(text) if text else {}
                except Exception:
                    payload = {"raw": text}
                return {
                    "success": ok,
                    "repo_name": repo_name,
                    "response_status": status,
                    "repo_full_name": payload.get("full_name"),
                    "repo_html_url": payload.get("html_url"),
                    "error": None if ok else payload.get("message", text)
                }
            
            elif action == "list_repos":
                status, text = request("GET", f"{api_base}/user/repos?per_page=20")
                ok = status == 200
                repos = []
                try:
                    data = json.loads(text) if text else []
                    repos = [item.get("full_name") for item in data if isinstance(item, dict)]
                except Exception:
                    repos = []
                return {
                    "success": ok,
                    "repos": repos,
                    "response_status": status,
                    "error": None if ok else text
                }
            
            elif action == "delete_repo":
                full_name = kwargs.get("name")
                if not full_name or "/" not in full_name:
                    return {"success": False, "error": "Repository name must be in 'owner/repo' format"}
                status, text = request("DELETE", f"{api_base}/repos/{full_name}")
                ok = status in (200, 202, 204)
                return {
                    "success": ok,
                    "repo_name": full_name,
                    "response_status": status,
                    "error": None if ok else text
                }
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = str(e)
            return {"success": False, "error": f"HTTPError {e.code}: {detail}"}
        except urllib.error.URLError as e:
            return {"success": False, "error": f"URLError: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        plan_save_dir: str = "./plans"
    ):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.enable_memory = enable_memory
        self.enable_planning = enable_planning

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
                save_dir=plan_save_dir
            )

        # Current execution state
        self.current_plan: Optional[ExecutionPlan] = None

        # Execution context and memory
        self.context: Dict[str, Any] = {}
        self.memory: List[ExecutionMemory] = []
        self.max_memory_size = 10

        # Statistics
        self.stats = defaultdict(int)

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

    # -------- NEW: message-first execution API --------
    async def run_messages(
        self,
        messages: List[Dict[str, Any]],
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Execute using OpenAI function calling given an existing message history.
        The Agent does NOT create system/user messages itself.

        Returns:
          - success: bool (true if all tool calls in the last turn succeeded or no tools were needed)
          - results: list[TaskResult as dict]
          - messages: updated message history
          - needs_user_input: bool
          - question: Optional[str] if the model requested info via {"ask_user": {...}}
        """
        results: List[TaskResult] = []
        iteration = 0
        needs_user_input = False
        pending_question: Optional[str] = None

        while iteration < max_iterations:
            iteration += 1
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    temperature=0.7
                )

                message = response.choices[0].message
                messages.append(message.dict())

                # No tool calls -> maybe model is done or is asking the user
                if not getattr(message, "tool_calls", None):
                    # Try to parse {"ask_user": {...}} convention from assistant content
                    content_text = (message.content or "")
                    content_stripped = content_text.strip()
                    if content_stripped.startswith("{") and "ask_user" in content_stripped:
                        try:
                            data = json.loads(content_stripped)
                        except json.JSONDecodeError:
                            # Handle cases where multiple JSON objects are concatenated
                            data = None
                            depth = 0
                            start_idx = None
                            in_string = False
                            escape = False
                            for idx, ch in enumerate(content_stripped):
                                if escape:
                                    escape = False
                                    continue
                                if ch == "\\":
                                    escape = True
                                    continue
                                if ch == '"' and not escape:
                                    in_string = not in_string
                                if in_string:
                                    continue
                                if ch == "{":
                                    if depth == 0:
                                        start_idx = idx
                                    depth += 1
                                elif ch == "}":
                                    depth -= 1
                                    if depth == 0 and start_idx is not None:
                                        first_json = content_stripped[start_idx:idx+1]
                                        try:
                                            data = json.loads(first_json)
                                        except Exception:
                                            data = None
                                        break
                        if isinstance(data, dict) and "ask_user" in data:
                            q = data["ask_user"].get("question") or ""
                            needs_user_input = True
                            pending_question = q
                    logger.info("No more tool calls issued by the model")
                    break

                # Execute tool calls
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    logger.info(f"Calling {tool_name} with args: {tool_args}")

                    # Execute with retry
                    task_result = await self._execute_tool_with_retry(
                        tool_name,
                        tool_args,
                        task_id=tool_call.id
                    )

                    results.append(task_result)

                    # Update context
                    self.context[tool_call.id] = task_result.result

                    # Add tool response to conversation
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(task_result.result)
                    }
                    messages.append(tool_response)

                    # If a critical failure occurs, stop this iteration batch
                    if not task_result.success and "critical" in str(task_result.error).lower():
                        logger.error(f"Critical failure: {task_result.error}")
                        break

            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}")
                break

        # Memory (optional, minimal): store a compact turn summary
        if self.enable_memory and results:
            self._store_memory("conversation_turn", results)

        success_count = sum(1 for r in results if r.success)
        return {
            "success": success_count == len(results) if results else True,
            "results": [
                {
                    "task_id": r.task_id,
                    "tool": r.tool,
                    "success": r.success,
                    "result": r.result,
                    "error": r.error,
                    "retries": r.retries,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in results
            ],
            "messages": messages,
            "needs_user_input": needs_user_input,
            "question": pending_question,
            "iterations": iteration,
            "stats": dict(self.stats),
        }

    # ------------- Planning path stays unchanged -------------
    async def execute_with_planning(self, goal: str) -> Dict[str, Any]:
        """Execute goal using planning system - Agent owns the execution loop"""

        if not self.enable_planning or not self.plan_manager:
            return await self.execute_with_function_calling(goal)

        try:
            # Create initial plan
            logger.info(f"Creating execution plan for: {goal}")
            plan = await self.plan_manager.create_plan(goal, self.context)
            self.current_plan = plan

            # Agent controls the execution loop
            while plan.status == "active":
                # Get next executable steps
                next_steps = self.plan_manager.get_next_steps(plan)

                if not next_steps:
                    # Check completion or blocking
                    if self._all_steps_complete(plan):
                        plan.status = "completed"
                        break

                    # Check for blocked steps
                    blocked_steps = self.plan_manager.get_blocked_steps(plan)
                    if blocked_steps:
                        logger.warning(f"{len(blocked_steps)} steps blocked by failures")

                        # Decide on replanning
                        if self._should_replan(plan):
                            execution_state = self._get_execution_state(plan)
                            plan = await self.plan_manager.replan(plan, execution_state)
                            self.current_plan = plan
                            continue
                        else:
                            plan.status = "failed"
                            break

                    # No more steps available
                    break

                # Execute steps (parallel and sequential)
                parallel_steps = [s for s in next_steps if s.can_parallel]
                sequential_steps = [s for s in next_steps if not s.can_parallel]

                # Execute parallel steps
                if parallel_steps:
                    tasks = [self._execute_step(step) for step in parallel_steps]
                    await asyncio.gather(*tasks)

                # Execute sequential steps
                for step in sequential_steps:
                    await self._execute_step(step)

                    # Check for critical failure
                    if step.state == StepState.FAILED and step.required:
                        if self._should_replan(plan):
                            execution_state = self._get_execution_state(plan)
                            plan = await self.plan_manager.replan(plan, execution_state)
                            self.current_plan = plan
                            break

                # Update and save plan after batch
                plan.update_stats()
                await self.plan_manager.save_plan(plan)

            # Store in memory
            if self.enable_memory:
                self._store_memory(goal, [
                    TaskResult(
                        task_id=step.id,
                        tool=step.tool,
                        success=step.state == StepState.COMPLETED,
                        result=step.result or {},
                        error=step.error
                    )
                    for step in plan.steps
                ])

            return {
                "success": plan.status == "completed",
                "goal": goal,
                "plan_id": plan.id,
                "status": plan.status,
                "completed_steps": plan.completed_steps,
                "failed_steps": plan.failed_steps,
                "total_steps": plan.total_steps,
                "context": plan.context,
                "plan_file": f"{self.plan_manager.save_dir}/plan_{plan.id}_v{plan.version}.md",
                "stats": dict(self.stats)
            }

        except Exception as e:
            logger.error(f"Planning execution failed: {e}")
            # Fallback to function calling
            return await self.execute_with_function_calling(goal)

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
                result = await tool.execute(**parameters)

                # Update statistics
                self.stats[f"{tool_name}_calls"] += 1

                if result.get("success"):
                    self.stats[f"{tool_name}_success"] += 1
                    return TaskResult(
                        task_id=task_id or f"task_{datetime.now().timestamp()}",
                        tool=tool_name,
                        success=True,
                        result=result,
                        retries=attempt
                    )

                last_error = result.get("error", "Unknown error")

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
        return TaskResult(
            task_id=task_id or f"task_{datetime.now().timestamp()}",
            tool=tool_name,
            success=False,
            result={},
            error=last_error,
            retries=self.max_retries
        )

    async def _fix_parameters(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        error: str
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to fix parameters based on error"""
        prompt = f"""
        Tool '{tool_name}' failed with error:
        {error}

        Original parameters:
        {json.dumps(parameters, indent=2)}

        Suggest corrected parameters that might fix this error.
        Return ONLY valid JSON with the corrected parameters.
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

    async def resume_plan(self, plan_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        """Resume execution of an existing plan"""

        if not self.plan_manager:
            return {"success": False, "error": "Planning not enabled"}

        # Load plan
        plan = await self.plan_manager.load_plan(plan_id, version)
        if not plan:
            return {"success": False, "error": f"Plan {plan_id} not found"}

        logger.info(f"Resuming plan {plan_id} v{plan.version}")
        self.current_plan = plan

        # Continue execution from current state
        return await self.execute_with_planning(plan.goal)

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
        plan_save_dir="./execution_plans"
    )
    
    # Example 1: Create and deploy a web application
    goal1 = """
    Create a simple Flask web application with:
    1. A homepage with a contact form
    2. Store submissions in a SQLite database
    3. Initialize Git repository
    4. Create GitHub repository and push code
    """
    
    print("=" * 60)
    print("Example 1: Web Application Development")
    print("=" * 60)
    
    result = await agent.execute_with_planning(goal1)
    
    print(f"Success: {result['success']}")
    print(f"Plan ID: {result.get('plan_id')}")
    print(f"Completed: {result.get('completed_steps')}/{result.get('total_steps')} steps")
    print(f"Plan saved to: {result.get('plan_file')}")
    
    # Example 2: Data analysis with dynamic replanning
    goal2 = """
    Analyze CSV files in the 'data' directory:
    1. Read all CSV files
    2. Generate summary statistics
    3. Create visualizations
    4. Write a comprehensive report
    """
    
    print("\n" + "=" * 60)
    print("Example 2: Data Analysis Pipeline")
    print("=" * 60)
    
    result = await agent.execute_with_planning(goal2)
    
    print(f"Success: {result['success']}")
    print(f"Status: {result.get('status')}")
    
    # Example 3: Resume a previous plan
    if result.get('plan_id'):
        print("\n" + "=" * 60)
        print("Example 3: Resuming Previous Plan")
        print("=" * 60)
        
        resume_result = await agent.resume_plan(result['plan_id'])
        print(f"Resume Success: {resume_result['success']}")
    
    # Example 4: Direct execution without planning
    print("\n" + "=" * 60)
    print("Example 4: Direct Execution with Function Calling")
    print("=" * 60)
    
    result = await agent.execute_with_function_calling(
        "Create a Python script that generates random passwords"
    )
    
    print(f"Success: {result['success']}")
    print(f"Tasks executed: {len(result['results'])}")
    print(f"Summary: {result['summary']}")
    
    # Get execution statistics
    print("\n" + "=" * 60)
    print("Execution Statistics")
    print("=" * 60)
    
    stats = agent.get_statistics()
    print(f"Total tool calls: {stats['total_calls']}")
    print(f"Success rate: {stats['overall_success_rate']:.1f}%")
    print(f"Memory entries: {stats['memory_entries']}")
    
    if stats['tools']:
        print("\nTool usage:")
        for tool, tool_stats in stats['tools'].items():
            print(f"  {tool}:")
            print(f"    Calls: {tool_stats['calls']}")
            print(f"    Success rate: {tool_stats['success_rate']:.1f}%")

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