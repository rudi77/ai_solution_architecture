from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import settings


def test_healthz(monkeypatch, tmp_path):
	# Isolate DB
	monkeypatch.setattr(settings, "sqlite_db_path", str(tmp_path / "api.db"), raising=False)
	app = create_app()
	client = TestClient(app)
	r = client.get("/healthz")
	assert r.status_code == 200
	assert r.json() == {"status": "ok"}


def test_agent_execute_stream_adk_unavailable(monkeypatch, tmp_path):
	# Force ADK unavailability so the endpoint streams a failure event
	monkeypatch.setattr(settings, "sqlite_db_path", str(tmp_path / "api.db"), raising=False)
	import app.agent.adk_adapter as adk_adapter
	monkeypatch.setattr(adk_adapter, "is_available", lambda: False, raising=False)
	app = create_app()
	client = TestClient(app)
	with client.stream("POST", "/api/agent/execute/stream", json={"prompt": "test", "engine": "adk"}) as r:
		assert r.status_code == 200
		data = "".join([chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in r.iter_raw()])
		assert "run_failed" in data

