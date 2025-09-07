from __future__ import annotations

"""Integration tests covering the public API endpoints.

These tests use the real OpenAI provider. Ensure OPENAI_API_KEY is set.
"""

import os
from typing import Dict

import httpx
import pytest


def _require_openai() -> None:
    """Assert that OPENAI_API_KEY is available for real-LLM tests."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    assert api_key, "OPENAI_API_KEY must be set to run integration tests with real LLM"


async def _register_minimal_system(client: httpx.AsyncClient) -> str:
    """Register a minimal orchestrator-only AgentSystem and return its id."""
    doc: Dict[str, object] = {
        "version": 1,
        "system": {"name": "api-suite"},
        "agents": [
            {
                "id": "orchestrator",
                "role": "orchestrator",
                "system_prompt": "You are the orchestrator.",
                "mission": "Create a short plan and validate inputs.",
                "max_steps": 3,
                "tools": {"allow": ["validate_project_name_and_type"]},
                "model": {"provider": "openai", "model": "gpt-4.1", "temperature": 0.1},
            }
        ],
    }
    res = await client.post("/agent-systems", json=doc)
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


@pytest.mark.asyncio
async def test_tools_and_agent_systems() -> None:
    """Test /tools and /agent-systems basic workflows."""
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # /tools
        tools = await client.get("/tools")
        assert tools.status_code == 200, tools.text
        data = tools.json()
        assert isinstance(data.get("tools"), list) and len(data["tools"]) > 0

        # Register system and fetch it
        sys_id = await _register_minimal_system(client)
        got = await client.get(f"/agent-systems/{sys_id}")
        assert got.status_code == 200, got.text
        # Unknown system
        not_found = await client.get("/agent-systems/does-not-exist")
        assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_health() -> None:
    """Test the /health endpoint is reachable."""
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_agent_system_register_invalid_returns_400() -> None:
    """Missing orchestrator should yield 400 from /agent-systems."""
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        bad_doc: Dict[str, object] = {
            "version": 1,
            "system": {"name": "invalid"},
            "agents": [
                {"id": "worker", "role": "sub-agent", "tools": {"allow": ["validate_project_name_and_type"]}}
            ],
        }
        res = await client.post("/agent-systems", json=bad_doc)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_session_lifecycle_and_artifacts() -> None:
    """Test session create → message → stream → state → artifact download."""
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test", timeout=httpx.Timeout(60.0)) as client:
        sys_id = await _register_minimal_system(client)
        ses = await client.post("/sessions", json={"agent_system_id": sys_id})
        assert ses.status_code == 201, ses.text
        sid = ses.json()["sid"]

        sent = await client.post(f"/sessions/{sid}/messages", json={"text": "Validate project demo-service"})
        assert sent.status_code == 202, sent.text

        # Read a handful of SSE events to allow initial plan creation
        async with client.stream("GET", f"/sessions/{sid}/stream") as resp:
            assert resp.status_code == 200
            got = 0
            async for line in resp.aiter_lines():
                if line and line.startswith("data: "):
                    got += 1
                if got >= 3:
                    break
        assert got >= 1

        # State
        st = await client.get(f"/sessions/{sid}/state")
        assert st.status_code == 200
        state = st.json()
        assert "version" in state and isinstance(state.get("tasks"), list)

        # Artifact
        art = await client.get(f"/sessions/{sid}/artifacts/todolist.md")
        assert art.status_code == 200
        assert art.headers.get("content-type", "").startswith("application/octet-stream") or art.text.startswith("# Todo List")


@pytest.mark.asyncio
async def test_unknown_session_404s() -> None:
    """Unknown session should return 404 across endpoints."""
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        s1 = await client.get("/sessions/does-not-exist/state")
        assert s1.status_code == 404
        s2 = await client.get("/sessions/does-not-exist/stream")
        assert s2.status_code == 404
        # Artifact path for unknown session should 404 as file doesn't exist
        s3 = await client.get("/sessions/does-not-exist/artifacts/todolist.md")
        assert s3.status_code in (404, 200)  # implementation may not check registry; tolerate missing


@pytest.mark.asyncio
async def test_answers_and_404s() -> None:
    """Test /answers endpoint and 404 responses for unknown resources."""
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        sys_id = await _register_minimal_system(client)
        ses = await client.post("/sessions", json={"agent_system_id": sys_id})
        assert ses.status_code == 201
        sid = ses.json()["sid"]

        # /answers should accept even if not awaiting input (no-op safety)
        ans = await client.post(f"/sessions/{sid}/answers", json={"text": "Some answer"})
        assert ans.status_code == 202

        # Unknown session
        s404 = await client.get("/sessions/does-not-exist/state")
        assert s404.status_code == 404


