from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Tuple, Dict, Any
import asyncio
import time
import uuid

from app.agent.planner import PlannedTask
from app.agent.runtime import registry
from app.agent.tools import run_tool


@dataclass
class AgentEvent:
	id: str
	type: str
	message: str
	run_id: str
	timestamp: float
	task_id: Optional[str] = None
	data: Optional[Dict[str, Any]] = None


def execute_tasks(tasks: List[PlannedTask]) -> List[AgentEvent]:
	# Minimal, synchronous execution simulator
	run_id = uuid.uuid4().hex
	registry.create(run_id, tasks)
	events: List[AgentEvent] = []
	for task in tasks:
		events.append(AgentEvent(id=f"{task.id}:start", type="task_started", message=task.title, run_id=run_id, timestamp=time.time()))
		task.status = "completed"
		events.append(AgentEvent(id=f"{task.id}:done", type="task_completed", message=task.title, run_id=run_id, timestamp=time.time()))
	return events


async def execute_tasks_stream(tasks: List[PlannedTask]) -> AsyncIterator[AgentEvent]:
	"""Asynchronously execute tasks and yield structured events.

	Yields run-level start/complete and per-task start/complete events.
	"""
	run_id = uuid.uuid4().hex
	registry.create(run_id, tasks)
	yield AgentEvent(id="run:start", type="run_started", message="Execution started", run_id=run_id, timestamp=time.time())
	for task in tasks:
		if registry.is_cancelled(run_id):
			yield AgentEvent(id="run:cancelled", type="run_cancelled", message="Execution cancelled", run_id=run_id, timestamp=time.time())
			return
		yield AgentEvent(id=f"{task.id}:start", type="task_started", message=task.title, run_id=run_id, timestamp=time.time(), task_id=task.id)

		# Emit a mock tool invocation if we can infer one from the task
		inferred = _infer_tool_for_task(task.title)
		if inferred is not None:
			tool, action = inferred
			yield AgentEvent(
				id=f"{task.id}:tool",
				type="tool_invoked",
				message=f"{tool}.{action}",
				run_id=run_id,
				timestamp=time.time(),
				task_id=task.id,
				data={"tool": tool, "action": action},
			)
			# Run mock tool
			result = await run_tool(tool, action, params={})
			yield AgentEvent(
				id=f"{task.id}:tool:result",
				type="tool_result",
				message=result.message,
				run_id=run_id,
				timestamp=time.time(),
				task_id=task.id,
				data={"status": result.status, **(result.data or {})},
			)

		# Simulate remaining work
		await asyncio.sleep(0.05)
		task.status = "completed"
		yield AgentEvent(id=f"{task.id}:done", type="task_completed", message=task.title, run_id=run_id, timestamp=time.time(), task_id=task.id)
	yield AgentEvent(id="run:done", type="run_completed", message="Execution completed", run_id=run_id, timestamp=time.time())


def _infer_tool_for_task(title: str) -> Optional[Tuple[str, str]]:
	"""Infer a mock tool and action name from a human-readable task title.

	This is a placeholder to mimic MCP/ADK tool calls in the stream.
	"""
	lowered = title.lower()
	if "repo" in lowered:
		return ("git", "create_repo")
	if "template" in lowered:
		return ("fs", "apply_templates")
	if "unit tests" in lowered or "tests" in lowered:
		return ("fs", "generate_tests")
	if "ci/cd" in lowered or "pipeline" in lowered:
		return ("ci", "setup_pipeline")
	return None


