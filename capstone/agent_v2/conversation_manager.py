# conversation_manager.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ConversationManager:
    session_id: str
    agent: Any
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def start(self, mission: Optional[str] = None):
        self.messages = self.agent.bootstrap_turn(mission)

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
