# ============================================
# PLANNER TOOL - Dynamic Plan Management
# ============================================
"""
PlannerTool allows the LLM to manage its own execution plan dynamically.
Replaces rigid TodoListManager with flexible, tool-based planning.
"""
from typing import Any, Dict, List, Optional

from capstone.agent_v2.tool import Tool


class PlannerTool(Tool):
    """
    Tool for LLM-controlled plan management.
    
    Supports creating, reading, updating, and marking tasks complete.
    State is serializable for persistence via StateManager.
    """
    
    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """
        Initialize PlannerTool with optional restored state.
        
        Args:
            initial_state: Previously saved state dict to restore from.
        """
        self._state: Dict[str, Any] = initial_state or {"tasks": []}
    
    @property
    def name(self) -> str:
        return "planner"
    
    @property
    def description(self) -> str:
        return (
            "Manage execution plan. Actions: "
            "'create_plan' (tasks: list of strings), "
            "'mark_done' (step_index: int), "
            "'read_plan' (no args), "
            "'update_plan' (add_steps: list, remove_indices: list)"
        )
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Custom schema for action-based tool."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'create_plan', 'mark_done', 'read_plan', 'update_plan'",
                    "enum": ["create_plan", "mark_done", "read_plan", "update_plan"]
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task descriptions (for create_plan)"
                },
                "step_index": {
                    "type": "integer",
                    "description": "Index of step to mark done (for mark_done)"
                },
                "add_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Steps to add (for update_plan)"
                },
                "remove_indices": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Indices of steps to remove (for update_plan)"
                }
            },
            "required": ["action"]
        }
    
    def get_state(self) -> Dict[str, Any]:
        """
        Export current state for serialization.
        
        Returns:
            Dict containing current tasks state.
        """
        return dict(self._state)
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Restore state from serialized data.
        
        Args:
            state: Previously saved state dict.
        """
        self._state = dict(state) if state else {"tasks": []}
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a planner action.
        
        Args:
            action: One of 'create_plan', 'mark_done', 'read_plan', 'update_plan'
            **kwargs: Action-specific parameters
            
        Returns:
            Dict with success status and result/error message.
        """
        action_map = {
            "create_plan": self._create_plan,
            "mark_done": self._mark_done,
            "read_plan": self._read_plan,
            "update_plan": self._update_plan,
        }
        
        handler = action_map.get(action)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown action: {action}. Valid: {list(action_map.keys())}"
            }
        
        return handler(**kwargs)
    
    def _create_plan(self, tasks: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Create a new plan from a list of task descriptions.
        
        Args:
            tasks: List of task description strings.
            
        Returns:
            Success dict with confirmation or error.
        """
        if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
            return {"success": False, "error": "tasks must be a non-empty list of strings"}
        
        self._state["tasks"] = [
            {"description": task, "done": False} for task in tasks
        ]
        
        return {
            "success": True,
            "message": f"Plan created with {len(tasks)} tasks.",
            "plan": self._format_plan()
        }
    
    def _mark_done(self, step_index: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Mark a specific step as completed.
        
        Args:
            step_index: Zero-based index of the step to mark done.
            
        Returns:
            Success dict with updated status or error.
        """
        if step_index is None:
            return {"success": False, "error": "step_index is required"}
        
        tasks = self._state.get("tasks", [])
        
        if not tasks:
            return {"success": False, "error": "No plan active"}
        
        if step_index < 0 or step_index >= len(tasks):
            return {
                "success": False,
                "error": f"step_index {step_index} out of bounds (0-{len(tasks)-1})"
            }
        
        tasks[step_index]["done"] = True
        
        return {
            "success": True,
            "message": f"Step {step_index} marked done.",
            "plan": self._format_plan()
        }
    
    def _read_plan(self, **kwargs) -> Dict[str, Any]:
        """
        Return the current plan as formatted Markdown.
        
        Returns:
            Success dict with plan string or 'No plan active'.
        """
        tasks = self._state.get("tasks", [])
        
        if not tasks:
            return {"success": True, "plan": "No plan active"}
        
        return {"success": True, "plan": self._format_plan()}
    
    def _update_plan(
        self,
        add_steps: Optional[List[str]] = None,
        remove_indices: Optional[List[int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Dynamically modify the plan by adding or removing steps.
        
        Args:
            add_steps: List of new task descriptions to append.
            remove_indices: List of indices to remove (processed in descending order).
            
        Returns:
            Success dict with updated plan or error.
        """
        tasks = self._state.get("tasks", [])
        
        # Remove steps first (in descending order to preserve indices)
        if remove_indices:
            for idx in sorted(remove_indices, reverse=True):
                if 0 <= idx < len(tasks):
                    tasks.pop(idx)
        
        # Add new steps
        if add_steps:
            for step in add_steps:
                tasks.append({"description": step, "done": False})
        
        self._state["tasks"] = tasks
        
        return {
            "success": True,
            "message": "Plan updated.",
            "plan": self._format_plan()
        }
    
    def _format_plan(self) -> str:
        """
        Format current plan as Markdown task list.
        
        Returns:
            Formatted string with checkbox syntax.
        """
        tasks = self._state.get("tasks", [])
        if not tasks:
            return "No plan active"
        
        lines = []
        for i, task in enumerate(tasks):
            checkbox = "[x]" if task["done"] else "[ ]"
            lines.append(f"{i}. {checkbox} {task['description']}")
        
        return "\n".join(lines)

