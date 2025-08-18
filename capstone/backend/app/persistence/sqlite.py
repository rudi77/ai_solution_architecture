from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable, List, Optional

from app.agent.planner import PlannedTask


def _connect(db_path: str) -> sqlite3.Connection:
	"""Create a new SQLite connection.

	A short-lived connection per operation keeps things simple and safe for asyncio.
	"""
	conn = sqlite3.connect(db_path)
	conn.execute("PRAGMA journal_mode=WAL;")
	conn.execute("PRAGMA synchronous=NORMAL;")
	return conn


def init_db(db_path: str) -> None:
	"""Initialize database schema if it does not exist."""
	Path(db_path).parent.mkdir(parents=True, exist_ok=True)
	with _connect(db_path) as conn:
		conn.executescript(
			"""
			CREATE TABLE IF NOT EXISTS conversations (
				id TEXT PRIMARY KEY
			);

			CREATE TABLE IF NOT EXISTS messages (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				conversation_id TEXT NOT NULL,
				role TEXT NOT NULL,
				content TEXT NOT NULL,
				ts REAL NOT NULL,
				FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
			);

			CREATE TABLE IF NOT EXISTS runs (
				id TEXT PRIMARY KEY,
				started_at REAL NOT NULL,
				completed_at REAL,
				cancelled INTEGER NOT NULL DEFAULT 0
			);

			CREATE TABLE IF NOT EXISTS tasks (
				id TEXT NOT NULL,
				run_id TEXT NOT NULL,
				title TEXT NOT NULL,
				status TEXT NOT NULL,
				PRIMARY KEY (id, run_id),
				FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
			);

			CREATE TABLE IF NOT EXISTS events (
				id TEXT NOT NULL,
				run_id TEXT NOT NULL,
				type TEXT NOT NULL,
				message TEXT NOT NULL,
				timestamp REAL NOT NULL,
				task_id TEXT,
				data TEXT,
				PRIMARY KEY (id, run_id),
				FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
			);
			"""
		)
		conn.commit()


def ensure_conversation(db_path: str, conversation_id: str) -> None:
	"""Insert a conversation row if it doesn't exist."""
	with _connect(db_path) as conn:
		conn.execute(
			"INSERT OR IGNORE INTO conversations(id) VALUES (?)",
			(conversation_id,),
		)
		conn.commit()


def conversation_exists(db_path: str, conversation_id: str) -> bool:
	"""Return True if a conversation row exists."""
	with _connect(db_path) as conn:
		cur = conn.execute(
			"SELECT 1 FROM conversations WHERE id = ? LIMIT 1",
			(conversation_id,),
		)
		row = cur.fetchone()
	return bool(row)


def add_message(db_path: str, conversation_id: str, role: str, content: str) -> None:
	"""Persist a chat message."""
	ensure_conversation(db_path, conversation_id)
	with _connect(db_path) as conn:
		conn.execute(
			"INSERT INTO messages(conversation_id, role, content, ts) VALUES (?,?,?,?)",
			(conversation_id, role, content, time.time()),
		)
		conn.commit()


def list_messages(db_path: str, conversation_id: str) -> List[dict]:
	"""Return messages for a conversation as simple dicts."""
	with _connect(db_path) as conn:
		cur = conn.execute(
			"SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
			(conversation_id,),
		)
		rows = cur.fetchall()
	return [{"role": r[0], "content": r[1]} for r in rows]


def create_run(db_path: str, run_id: str) -> None:
	with _connect(db_path) as conn:
		conn.execute(
			"INSERT OR IGNORE INTO runs(id, started_at, cancelled) VALUES (?,?,0)",
			(run_id, time.time()),
		)
		conn.commit()


def save_tasks(db_path: str, run_id: str, tasks: Iterable[PlannedTask]) -> None:
	to_insert = [(t.id, run_id, t.title, t.status) for t in tasks]
	with _connect(db_path) as conn:
		conn.executemany(
			"INSERT OR REPLACE INTO tasks(id, run_id, title, status) VALUES (?,?,?,?)",
			to_insert,
		)
		conn.commit()


def update_task_status(db_path: str, run_id: str, task_id: str, status: str) -> None:
	with _connect(db_path) as conn:
		conn.execute(
			"UPDATE tasks SET status = ? WHERE run_id = ? AND id = ?",
			(status, run_id, task_id),
		)
		conn.commit()


def log_event(
	db_path: str,
	run_id: str,
	event_id: str,
	event_type: str,
	message: str,
	timestamp: float,
	task_id: Optional[str] = None,
	data: Optional[dict] = None,
) -> None:
	with _connect(db_path) as conn:
		conn.execute(
			"INSERT OR REPLACE INTO events(id, run_id, type, message, timestamp, task_id, data) VALUES (?,?,?,?,?,?,?)",
			(
				event_id,
				run_id,
				event_type,
				message,
				timestamp,
				task_id,
				json.dumps(data) if data is not None else None,
			),
		)
		conn.commit()


def complete_run(db_path: str, run_id: str) -> None:
	with _connect(db_path) as conn:
		conn.execute(
			"UPDATE runs SET completed_at = ? WHERE id = ?",
			(time.time(), run_id),
		)
		conn.commit()


def cancel_run(db_path: str, run_id: str) -> None:
	with _connect(db_path) as conn:
		conn.execute(
			"UPDATE runs SET cancelled = 1, completed_at = COALESCE(completed_at, ?) WHERE id = ?",
			(time.time(), run_id),
		)
		conn.commit()


