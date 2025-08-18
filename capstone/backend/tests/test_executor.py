from __future__ import annotations

import asyncio
from typing import List

from app.agent.planner import PlannedTask
from app.agent.executor import execute_tasks_stream, _infer_tool_for_task
from app.persistence.sqlite import init_db
from app.settings import settings


def test_infer_tool_for_task_mapping():
	assert _infer_tool_for_task("Git Repo anlegen (demo)") == ("git", "create_repo")
	assert _infer_tool_for_task("Templates einfügen") == ("fs", "apply_templates")
	assert _infer_tool_for_task("Unit Tests generieren") == ("fs", "generate_tests")
	assert _infer_tool_for_task("CI/CD Pipeline konfigurieren") == ("ci", "setup_pipeline")


async def _collect_events(tasks: List[PlannedTask]) -> list:
	# Use a temporary on-disk SQLite DB for the run
	init_db(settings.sqlite_db_path)
	events = []
	async for evt in execute_tasks_stream(tasks):
		events.append(evt)
	return events


def test_execute_tasks_stream(tmp_path, monkeypatch):
	# Route DB to a temporary path
	monkeypatch.setattr(settings, "sqlite_db_path", str(tmp_path / "test.db"), raising=False)
	# Compose a task list that triggers all tool types
	tasks = [
		PlannedTask(id="t1", title="Git Repo anlegen (demo)"),
		PlannedTask(id="t2", title="Templates einfügen (fastapi, python)"),
		PlannedTask(id="t3", title="Unit Tests generieren"),
		PlannedTask(id="t4", title="CI/CD Pipeline konfigurieren (github-actions)"),
	]
	loop = asyncio.new_event_loop()
	try:
		asyncio.set_event_loop(loop)
		events = loop.run_until_complete(_collect_events(tasks))
	finally:
		loop.close()

	# Validate lifecycle events are present
	types = [e.type for e in events]
	assert "run_started" in types
	assert "run_completed" in types
	# Ensure each task has start and completion
	for t in tasks:
		assert any(e.type == "task_started" and e.task_id == t.id for e in events)
		assert any(e.type == "task_completed" and e.task_id == t.id for e in events)
	# Ensure tool invocations and results occurred
	assert any(e.type == "tool_invoked" for e in events)
	assert any(e.type == "tool_result" for e in events)

