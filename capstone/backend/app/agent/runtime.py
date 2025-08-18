from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.agent.planner import PlannedTask


class RunRegistry:
	"""In-memory registry for running executions with simple cancellation flags."""

	def __init__(self) -> None:
		self._lock = threading.Lock()
		self._runs: Dict[str, Dict[str, object]] = {}

	def create(self, run_id: str, tasks: List[PlannedTask]) -> None:
		with self._lock:
			self._runs[run_id] = {"cancelled": False, "tasks": tasks}

	def cancel(self, run_id: str) -> bool:
		with self._lock:
			entry = self._runs.get(run_id)
			if entry is None:
				return False
			entry["cancelled"] = True
			return True

	def is_cancelled(self, run_id: str) -> bool:
		with self._lock:
			entry = self._runs.get(run_id)
			return bool(entry and entry.get("cancelled"))

	def get_tasks(self, run_id: str) -> Optional[List[PlannedTask]]:
		with self._lock:
			entry = self._runs.get(run_id)
			if entry is None:
				return None
			return entry.get("tasks")  # type: ignore[return-value]


registry = RunRegistry()


