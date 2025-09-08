from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SessionEntry:
    """
    Represents a single session entry in the session store.

    Attributes:
        id (str): The unique identifier for the session.
        agent (Any): The agent instance associated with this session.
        created_at (str): The ISO-formatted timestamp when the session was created.
        last_activity (str): The ISO-formatted timestamp of the last activity in this session.
    """
    id: str
    agent: Any
    created_at: str
    last_activity: str


class SessionStore:
    """
    Manages the lifecycle and storage of session entries.

    This class provides methods to create, retrieve, and update session entries,
    which are stored in an in-memory dictionary keyed by session ID.
    """

    def __init__(self) -> None:
        """
        Initializes the session store with an empty dictionary to hold session entries.
        """
        self._items: Dict[str, SessionEntry] = {}

    def create(self, sid: str, agent: Any) -> SessionEntry:
        """
        Creates a new session entry and stores it in the session store.

        Args:
            sid (str): The unique session identifier.
            agent (Any): The agent instance to associate with this session.

        Returns:
            SessionEntry: The newly created session entry.
        """
        now = datetime.utcnow().isoformat()
        entry = SessionEntry(id=sid, agent=agent, created_at=now, last_activity=now)
        self._items[sid] = entry
        return entry

    def get(self, sid: str) -> Optional[SessionEntry]:
        """
        Retrieves a session entry by its session ID.

        Args:
            sid (str): The session identifier.

        Returns:
            Optional[SessionEntry]: The session entry if found, otherwise None.
        """
        return self._items.get(sid)

    def touch(self, sid: str) -> None:
        """
        Updates the last_activity timestamp of a session entry to the current time.

        Args:
            sid (str): The session identifier.

        This method does nothing if the session ID does not exist in the store.
        """
        if sid in self._items:
            self._items[sid].last_activity = datetime.utcnow().isoformat()


