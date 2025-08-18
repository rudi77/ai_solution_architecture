from __future__ import annotations

from app.persistence.sqlite import init_db, add_message, list_messages, create_run, save_tasks, log_event, complete_run
from app.agent.planner import PlannedTask


def test_message_persistence_roundtrip(tmp_path):
	db = str(tmp_path / "app.db")
	init_db(db)
	conv_id = "conv-1"
	add_message(db, conv_id, "user", "hello")
	add_message(db, conv_id, "assistant", "hi")
	msgs = list_messages(db, conv_id)
	assert msgs == [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]


def test_run_and_events(tmp_path):
	db = str(tmp_path / "app.db")
	init_db(db)
	run_id = "run-123"
	create_run(db, run_id)
	save_tasks(db, run_id, [PlannedTask(id="t1", title="Test Task")])
	log_event(db, run_id, "e1", "task_started", "Test Task", 123.45, task_id="t1", data={"k": "v"})
	complete_run(db, run_id)
	# No exception implies schema and basic operations work
	assert True

