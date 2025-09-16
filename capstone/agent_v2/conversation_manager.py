# conversation_manager.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from capstone.agent_v2.hybrid_agent import HybridAgent


@dataclass
class ConversationManager:
    session_id: str
    agent: HybridAgent
    plan_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    async def start(self, mission: str) -> Dict[str, Any]:
        out = await self.agent.execute(mission, session_id=self.session_id, plan_id=self.plan_id)
        self.plan_id = out.get("plan_id", self.plan_id)
        msgs = out.get("messages")
        if isinstance(msgs, list):
            self.history = msgs
        return out

    async def user_says(self, text: str) -> Dict[str, Any]:
        out = await self.agent.execute(
            session_id=self.session_id,
            plan_id=self.plan_id,
            user_message=text,
        )
        self.plan_id = out.get("plan_id", self.plan_id)
        msgs = out.get("messages")
        if isinstance(msgs, list):
            self.history = msgs
        return out
