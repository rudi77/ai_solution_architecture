from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Message:
	role: str
	content: str


@dataclass
class Conversation:
	id: str
	messages: List[Message] = field(default_factory=list)
	missing_fields: List[str] = field(default_factory=list)


class InMemoryConversationStore:
	def __init__(self) -> None:
		self._conversations: Dict[str, Conversation] = {}

	def create(self, conversation_id: str) -> Conversation:
		conversation = Conversation(id=conversation_id)
		self._conversations[conversation_id] = conversation
		return conversation

	def get(self, conversation_id: str) -> Optional[Conversation]:
		return self._conversations.get(conversation_id)

	def add_message(self, conversation_id: str, role: str, content: str) -> Conversation:
		conversation = self._conversations.setdefault(conversation_id, Conversation(id=conversation_id))
		conversation.messages.append(Message(role=role, content=content))
		return conversation


store = InMemoryConversationStore()


