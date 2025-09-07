from __future__ import annotations

import asyncio
import os
from typing import List

import httpx
import pytest


@pytest.mark.asyncio
async def test_e2e_register_session_stream_state() -> None:
    """End-to-end test using the real OpenAI provider if OPENAI_API_KEY is set.

    Flow:
    - Register a minimal AgentSystem (orchestrator only)
    - Create a session
    - Send a message
    - Consume a few SSE events from the stream
    - Inspect session state
    """

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    assert api_key, "OPENAI_API_KEY must be set to run integration tests with real LLM"

    from capstone.backend.app.main import app

    timeout = httpx.Timeout(connect=20.0, read=30.0, write=20.0, pool=20.0)
    async with httpx.AsyncClient(app=app, base_url="http://test", timeout=timeout) as client:
        register_doc = {
            "version": 1,
            "system": {"name": "e2e-smoke"},
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
        reg = await client.post("/agent-systems", json=register_doc)
        assert reg.status_code == 201, reg.text
        system_id = reg.json()["id"]

        ses = await client.post("/sessions", json={"agent_system_id": system_id})
        assert ses.status_code == 201, ses.text
        sid = ses.json()["sid"]

        msg = await client.post(
            f"/sessions/{sid}/messages",
            json={"text": "Please validate project name 'demo-service' and start."},
        )
        assert msg.status_code == 202, msg.text

        events: List[str] = []
        async with client.stream("GET", f"/sessions/{sid}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload = line[len("data: ") :].strip()
                    if payload:
                        events.append(payload)
                if len(events) >= 3:
                    break
        assert len(events) >= 1, "Expected at least one SSE data event"

        st = await client.get(f"/sessions/{sid}/state")
        assert st.status_code == 200, st.text
        state = st.json()
        assert "version" in state
        assert "tasks" in state


