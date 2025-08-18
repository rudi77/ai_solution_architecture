from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Tuple, Dict, Any
import asyncio
import time
import uuid

from app.agent.planner import PlannedTask
from app.agent.runtime import registry
from app.agent.tools import run_tool
from app.settings import settings
from app.persistence import sqlite as sq


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
	sq.create_run(settings.sqlite_db_path, run_id)
	sq.save_tasks(settings.sqlite_db_path, run_id, tasks)
	events: List[AgentEvent] = []
	for task in tasks:
		evt = AgentEvent(id=f"{task.id}:start", type="task_started", message=task.title, run_id=run_id, timestamp=time.time())
		events.append(evt)
		sq.log_event(settings.sqlite_db_path, run_id, evt.id, evt.type, evt.message, evt.timestamp, task_id=None, data=None)
		task.status = "completed"
		sq.update_task_status(settings.sqlite_db_path, run_id, task.id, task.status)
		evt2 = AgentEvent(id=f"{task.id}:done", type="task_completed", message=task.title, run_id=run_id, timestamp=time.time())
		events.append(evt2)
		sq.log_event(settings.sqlite_db_path, run_id, evt2.id, evt2.type, evt2.message, evt2.timestamp, task_id=None, data=None)
	sq.complete_run(settings.sqlite_db_path, run_id)
	return events


async def execute_tasks_stream(tasks: List[PlannedTask]) -> AsyncIterator[AgentEvent]:
	"""Asynchronously execute tasks and yield structured events.

	Yields run-level start/complete and per-task start/complete events.
	"""
	run_id = uuid.uuid4().hex
	registry.create(run_id, tasks)
	sq.create_run(settings.sqlite_db_path, run_id)
	sq.save_tasks(settings.sqlite_db_path, run_id, tasks)
	start_evt = AgentEvent(id="run:start", type="run_started", message="Execution started", run_id=run_id, timestamp=time.time())
	sq.log_event(settings.sqlite_db_path, run_id, start_evt.id, start_evt.type, start_evt.message, start_evt.timestamp)
	yield start_evt
	for task in tasks:
		if registry.is_cancelled(run_id):
			cancel_evt = AgentEvent(id="run:cancelled", type="run_cancelled", message="Execution cancelled", run_id=run_id, timestamp=time.time())
			sq.log_event(settings.sqlite_db_path, run_id, cancel_evt.id, cancel_evt.type, cancel_evt.message, cancel_evt.timestamp)
			sq.cancel_run(settings.sqlite_db_path, run_id)
			yield cancel_evt
			return
		start_task_evt = AgentEvent(id=f"{task.id}:start", type="task_started", message=task.title, run_id=run_id, timestamp=time.time(), task_id=task.id)
		sq.log_event(settings.sqlite_db_path, run_id, start_task_evt.id, start_task_evt.type, start_task_evt.message, start_task_evt.timestamp, task_id=task.id)
		yield start_task_evt

		# Emit a mock tool invocation if we can infer one from the task
		inferred = _infer_tool_for_task(task.title)
		if inferred is not None:
			tool, action = inferred
			tool_evt = AgentEvent(
				id=f"{task.id}:tool",
				type="tool_invoked",
				message=f"{tool}.{action}",
				run_id=run_id,
				timestamp=time.time(),
				task_id=task.id,
				data={"tool": tool, "action": action},
			)
			sq.log_event(settings.sqlite_db_path, run_id, tool_evt.id, tool_evt.type, tool_evt.message, tool_evt.timestamp, task_id=task.id, data=tool_evt.data)
			yield tool_evt
			# Run mock tool
			result = await run_tool(tool, action, params={})
			tool_res_evt = AgentEvent(
				id=f"{task.id}:tool:result",
				type="tool_result",
				message=result.message,
				run_id=run_id,
				timestamp=time.time(),
				task_id=task.id,
				data={"status": result.status, **(result.data or {})},
			)
			sq.log_event(settings.sqlite_db_path, run_id, tool_res_evt.id, tool_res_evt.type, tool_res_evt.message, tool_res_evt.timestamp, task_id=task.id, data=tool_res_evt.data)
			yield tool_res_evt

		# Simulate remaining work
		await asyncio.sleep(0.05)
		task.status = "completed"
		sq.update_task_status(settings.sqlite_db_path, run_id, task.id, task.status)
		completed_evt = AgentEvent(id=f"{task.id}:done", type="task_completed", message=task.title, run_id=run_id, timestamp=time.time(), task_id=task.id)
		sq.log_event(settings.sqlite_db_path, run_id, completed_evt.id, completed_evt.type, completed_evt.message, completed_evt.timestamp, task_id=task.id)
		yield completed_evt
	end_evt = AgentEvent(id="run:done", type="run_completed", message="Execution completed", run_id=run_id, timestamp=time.time())
	sq.log_event(settings.sqlite_db_path, run_id, end_evt.id, end_evt.type, end_evt.message, end_evt.timestamp)
	sq.complete_run(settings.sqlite_db_path, run_id)
	yield end_evt


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


