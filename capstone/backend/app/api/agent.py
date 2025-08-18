from typing import List, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.planner import plan_service_creation, PlannedTask
from app.agent.executor import execute_tasks, execute_tasks_stream
from fastapi.responses import StreamingResponse
import json
from app.agent.runtime import registry
from app.agent import adk_adapter
from app.settings import settings
from app.persistence.sqlite import cancel_run


router = APIRouter(prefix="/agent", tags=["agent"])


class ExecuteRequest(BaseModel):
	prompt: str = Field(min_length=3)
	engine: Literal["auto", "builtin", "adk"] = Field(default="auto")


class TaskModel(BaseModel):
	id: str
	title: str
	status: str


class EventModel(BaseModel):
	id: str
	type: str
	message: str


class ExecuteResponse(BaseModel):
	tasks: List[TaskModel]
	events: List[EventModel]


@router.post("/execute", response_model=ExecuteResponse)
async def execute(payload: ExecuteRequest) -> ExecuteResponse:
	from fastapi import HTTPException

	raise HTTPException(status_code=400, detail="Only ADK streaming is supported. Use /api/agent/execute/stream")


@router.post("/execute/stream")
async def execute_stream(payload: ExecuteRequest) -> StreamingResponse:
	"""Server-Sent Events stream of agent execution using ADK only."""

	async def event_generator():
		async for evt in adk_adapter.execute_stream(payload.prompt):
			yield f"event: {evt.get('type','message')}\n" + f"data: {json.dumps(evt)}\n\n"

	return StreamingResponse(event_generator(), media_type="text/event-stream")


class CancelRequest(BaseModel):
	run_id: str = Field(min_length=8)


@router.post("/cancel")
async def cancel(payload: CancelRequest) -> dict:
	success = registry.cancel(payload.run_id)
	if success:
		cancel_run(settings.sqlite_db_path, payload.run_id)
	return {"ok": success}


