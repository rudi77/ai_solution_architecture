from __future__ import annotations

"""Artifact lifecycle test: 404 before processing, 200 after stream produces Markdown."""

import os
import httpx
import pytest


def _require_openai() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    assert api_key, "OPENAI_API_KEY must be set to run artifact tests"


@pytest.mark.asyncio
async def test_artifact_created_after_stream() -> None:
    _require_openai()
    from capstone.backend.app.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test", timeout=httpx.Timeout(60.0)) as client:
        # Register minimal system
        reg = await client.post(
            "/agent-systems",
            json={
                "version": 1,
                "system": {"name": "artifact-flow"},
                "agents": [
                    {
                        "id": "orchestrator",
                        "role": "orchestrator",
                        "system_prompt": "You are the orchestrator.",
                        "mission": "Create a plan and render todolist.",
                        "max_steps": 3,
                        "tools": {"allow": ["validate_project_name_and_type"]},
                        "model": {"provider": "openai", "model": "gpt-4.1", "temperature": 0.1},
                    }
                ],
            },
        )
        assert reg.status_code == 201
        sys_id = reg.json()["id"]

        # Create session
        ses = await client.post("/sessions", json={"agent_system_id": sys_id})
        assert ses.status_code == 201
        sid = ses.json()["sid"]

        # Artifact should be missing before any processing
        pre = await client.get(f"/sessions/{sid}/artifacts/todolist.md")
        assert pre.status_code == 404

        # Send message
        sent = await client.post(
            f"/sessions/{sid}/messages",
            json={"text": "Validate project demo-service and start."},
        )
        assert sent.status_code == 202

        # Consume some events to trigger plan creation + rendering
        async with client.stream("GET", f"/sessions/{sid}/stream") as resp:
            assert resp.status_code == 200
            got = 0
            async for line in resp.aiter_lines():
                if line and line.startswith("data: "):
                    got += 1
                if got >= 3:
                    break
        assert got >= 1

        # Artifact should now exist
        post = await client.get(f"/sessions/{sid}/artifacts/todolist.md")
        assert post.status_code == 200
        assert post.text.startswith("# Todo List")


