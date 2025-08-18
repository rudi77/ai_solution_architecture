from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.settings import settings
from app.persistence import sqlite as sq


@dataclass
class Message:
	role: str
	content: str


@dataclass
class Conversation:
	id: str
	messages: List[Message] = field(default_factory=list)
	missing_fields: List[str] = field(default_factory=list)


class SQLiteConversationStore:
	def __init__(self, db_path: str) -> None:
		self._db_path = db_path

	def create(self, conversation_id: str) -> Conversation:
		sq.ensure_conversation(self._db_path, conversation_id)
		return Conversation(id=conversation_id, messages=[])

	def get(self, conversation_id: str) -> Optional[Conversation]:
		if not sq.conversation_exists(self._db_path, conversation_id):
			return None
		msgs = sq.list_messages(self._db_path, conversation_id)
		return Conversation(id=conversation_id, messages=[Message(**m) for m in msgs])

	def add_message(self, conversation_id: str, role: str, content: str) -> Conversation:
		sq.add_message(self._db_path, conversation_id, role, content)
		msgs = sq.list_messages(self._db_path, conversation_id)
		return Conversation(id=conversation_id, messages=[Message(**m) for m in msgs])


store = SQLiteConversationStore(settings.sqlite_db_path)


