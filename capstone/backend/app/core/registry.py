from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class AgentSystemEntry:
    id: str
    factory: Callable[[], Any]
    resolved: Dict[str, Any]


class AgentSystemRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, AgentSystemEntry] = {}

    def register(self, system_id: str, factory: Callable[[], Any], resolved: Dict[str, Any]) -> None:
        self._items[system_id] = AgentSystemEntry(id=system_id, factory=factory, resolved=resolved)

    def get_factory(self, system_id: str) -> Optional[Callable[[], Any]]:
        item = self._items.get(system_id)
        return item.factory if item else None

    def get_resolved(self, system_id: str) -> Optional[Dict[str, Any]]:
        item = self._items.get(system_id)
        return dict(item.resolved) if item else None

    def list_ids(self) -> list[str]:
        return list(self._items.keys())


