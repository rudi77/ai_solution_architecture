# ============================================
# ASK USER TOOL (first-class)
# ============================================

from ast import Dict, List
from typing import Any
from capstone.agent_v2.tool import Tool


class AskUserTool(Tool):
    """Model-invoked prompt to request missing info from a human."""

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return "Ask the user for missing info to proceed. Returns a structured question payload."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "One clear question"},
                "missing": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question"],
        }

    async def execute(self, question: str, missing: List[str] = None, **kwargs) -> Dict[str, Any]:
        return {"success": True, "question": question, "missing": missing or []}
