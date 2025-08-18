from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.agent.planner import PlannedTask


@dataclass
class AgentEvent:
	id: str
	type: str
	message: str


def execute_tasks(tasks: List[PlannedTask]) -> List[AgentEvent]:
	# Minimal, synchronous execution simulator
	events: List[AgentEvent] = []
	for task in tasks:
		events.append(AgentEvent(id=f"{task.id}:start", type="task_started", message=task.title))
		task.status = "completed"
		events.append(AgentEvent(id=f"{task.id}:done", type="task_completed", message=task.title))
	return events


