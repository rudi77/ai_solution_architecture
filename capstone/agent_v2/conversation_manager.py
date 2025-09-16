# conversation_manager.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ConversationManager:
    session_id: str
    agent: Any
    plan_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    async def start(self, mission: str) -> Dict[str, Any]:
        out = await self.agent.execute(mission, session_id=self.session_id, plan_id=self.plan_id)
        self.plan_id = out.get("plan_id", self.plan_id)
        return out

    async def user_says(self, text: str) -> Dict[str, Any]:
        out = await self.agent.execute(
            session_id=self.session_id,
            plan_id=self.plan_id,
            user_message=text,
        )
        self.plan_id = out.get("plan_id", self.plan_id)
        return out
