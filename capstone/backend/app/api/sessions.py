from __future__ import annotations

import asyncio
import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse, FileResponse
from fastapi import HTTPException

from ..core.session_store import SessionStore
from ..core.registry import AgentSystemRegistry
from capstone.prototype.todolist_md import get_todolist_path


router = APIRouter()
sessions = SessionStore()
# Reuse the same registry instance used by agent_systems module
from .agent_systems import registry as systems


class CreateSessionRequest(BaseModel):
    agent_system_id: str
    user_id: str | None = None


class CreateSessionResponse(BaseModel):
    sid: str


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    factory = systems.get_factory(body.agent_system_id)
    if not factory:
        raise HTTPException(status_code=404, detail="agent system not found")
    agent = factory()
    sid = str(uuid.uuid4())
    sessions.create(sid, agent)
    return CreateSessionResponse(sid=sid)


class MessageBody(BaseModel):
    text: str


@router.post("/sessions/{sid}/messages", status_code=202)
async def post_message(sid: str, body: MessageBody) -> dict:
    entry = sessions.get(sid)
    if not entry:
        raise HTTPException(status_code=404, detail="session not found")
    # Store last message to be picked up by /stream
    entry.agent.context["recent_user_message"] = body.text
    sessions.touch(sid)
    return {"status": "accepted"}


@router.get("/sessions/{sid}/stream")
async def stream(sid: str) -> StreamingResponse:
    entry = sessions.get(sid)
    if not entry:
        raise HTTPException(status_code=404, detail="session not found")

    async def event_gen():
        user_text = entry.agent.context.get("recent_user_message", "")
        async for chunk in entry.agent.process_request(user_text, session_id=sid):
            # Ensure each event is a string line; chunk may already be text
            payload = chunk if isinstance(chunk, str) else str(chunk)
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class AnswerBody(BaseModel):
    text: str


@router.post("/sessions/{sid}/answers", status_code=202)
async def post_answer(sid: str, body: AnswerBody) -> dict:
    entry = sessions.get(sid)
    if not entry:
        raise HTTPException(status_code=404, detail="session not found")
    entry.agent.context["recent_user_message"] = body.text
    sessions.touch(sid)
    return {"status": "accepted"}


@router.get("/sessions/{sid}/state")
async def get_state(sid: str) -> dict:
    entry = sessions.get(sid)
    if not entry:
        raise HTTPException(status_code=404, detail="session not found")
    ctx = entry.agent.context or {}
    return {
        "version": ctx.get("version"),
        "awaiting_user_input": ctx.get("awaiting_user_input"),
        "tasks": ctx.get("tasks", []),
        "blocker": ctx.get("blocker"),
    }


@router.get("/sessions/{sid}/artifacts/todolist.md")
async def get_todolist(sid: str) -> FileResponse:
    path = get_todolist_path(session_id=sid)
    try:
        # get_todolist_path returns a Path. If it doesn't exist, return 404 instead of raising at FileResponse.
        if not path.exists():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(str(path))
    except HTTPException:
        raise
    except Exception:
        # For any unexpected error, still return 404 to keep API surface stable
        raise HTTPException(status_code=404, detail="artifact not found")


