# conversation_manager.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

ASK_USER_INSTRUCTION = """
You are a task-oriented assistant. If you need information from the user to proceed,
respond with ONLY this JSON (no extra text):
{"ask_user": {"question": "<one clear question>", "missing": ["<field1>", "..."]}}
"""

@dataclass
class ConversationManager:
    session_id: str
    agent: Any
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def _base_system_prompt(self) -> str:
        mem = self.agent.get_memory_context(limit=3) or ""
        mem_block = f"\n\nPrevious execution context:\n{mem}" if mem else ""
        return (
            "You are TaskForce Assistant. Use tools prudently. "
            "If you lack required info, ask the user using the JSON schema described."
            f"{mem_block}\n\n"
        ) + ASK_USER_INSTRUCTION

    def start(self, mission: Optional[str] = None):
        self.messages = [{"role": "system", "content": self._base_system_prompt()}]
        if mission:
            self.messages.append({"role": "user", "content": mission})

    async def user_says(self, text: str) -> Dict[str, Any]:
        """Append user input and run a model turn."""
        self.messages.append({"role": "user", "content": text})
        result = await self.agent.run_messages(self.messages)
        self.messages = result["messages"]
        return {
            "needs_user_input": result.get("needs_user_input", False),
            "question": result.get("question"),
            "results": result.get("results", []),
        }

    async def run_mission(self, mission: str) -> Dict[str, Any]:
        """Kick off a mission and handle potential back-and-forth."""
        self.start(mission)
        result = await self.agent.run_messages(self.messages)
        self.messages = result["messages"]
        return result

    def history(self) -> List[Dict[str, Any]]:
        return list(self.messages)
