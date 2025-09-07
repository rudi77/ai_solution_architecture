from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SessionEntry:
    id: str
    agent: Any
    created_at: str
    last_activity: str


class SessionStore:
    def __init__(self) -> None:
        self._items: Dict[str, SessionEntry] = {}

    def create(self, sid: str, agent: Any) -> SessionEntry:
        now = datetime.utcnow().isoformat()
        entry = SessionEntry(id=sid, agent=agent, created_at=now, last_activity=now)
        self._items[sid] = entry
        return entry

    def get(self, sid: str) -> Optional[SessionEntry]:
        return self._items.get(sid)

    def touch(self, sid: str) -> None:
        if sid in self._items:
            self._items[sid].last_activity = datetime.utcnow().isoformat()


