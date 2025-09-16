from dataclasses import asdict, dataclass, field
import datetime
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

# create logger from existing logging config
logger = logging.getLogger(__name__)


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
    
    # Execution details
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['state'] = self.state.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        """Create from dictionary"""
        data = data.copy()
        if 'state' in data:
            data['state'] = StepState(data['state'])
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
    
    def __init__(self, 
        model_client, 
        model: str, 
        available_tools: Dict[str, Any], 
        save_dir: str = "./plans", 
        *, 
        verbose: bool = False, 
        pretty: bool = True, 
        redactor: Optional[Any] = None):
        
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
        
        structure_block = """
{
  "steps": [
    {
      "id": "unique_step_id",
      "description": "Clear description of what this step does",
      "tool": "tool_name",
      "parameters": {},
      "depends_on": ["previous_step_id"]
    }
  ],
  "notes": ["Any important considerations"]
}
"""

        prompt = (
            "Create a concise, step-by-step execution plan for this goal:\n"
            f"{goal}\n"
            f"{context_str}\n\n"
            "Available tools:\n"
            f"{tools_desc}\n\n"
            "Create a plan with:\n"
            "1. Clear, actionable steps\n"
            "2. Minimal per-step fields: id, description, tool, parameters, depends_on\n"
            "3. Parameters must conform to the selected tool parameters_schema\n\n"
            "PowerShell notes:\n"
            "- Use valid PowerShell syntax (not bash). Examples: New-Item -ItemType Directory -Path \"C:\\path\"; Set-Content; Get-ChildItem\n"
            "- Always include a 'command' string that is executable under PowerShell\n"
            "- Provide a 'cwd' when file operations depend on a working directory (default repo root if unsure)\n\n"
            "Return a JSON object with this structure:\n"
            f"{structure_block}"
        )
        
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
                    depends_on=step_data.get("depends_on", [])
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
                    depends_on=step_data.get("depends_on", [])
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
        failed_ids = {s.id for s in plan.steps if s.state == StepState.FAILED}
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
            # timestamps removed from PlanStep; ignore started_at/completed_at
            
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

