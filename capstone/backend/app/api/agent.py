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
	tasks: List[PlannedTask] = plan_service_creation(payload.prompt)
	events = execute_tasks(tasks)
	return ExecuteResponse(
		tasks=[TaskModel(id=t.id, title=t.title, status=t.status) for t in tasks],
		events=[EventModel(id=e.id, type=e.type, message=e.message) for e in events],
	)


@router.post("/execute/stream")
async def execute_stream(payload: ExecuteRequest) -> StreamingResponse:
	"""Server-Sent Events stream of agent execution."""
	tasks: List[PlannedTask] = plan_service_creation(payload.prompt)

	async def event_generator():
		# Engine selection: request overrides settings
		selected = payload.engine if payload.engine != "auto" else settings.agent_engine
		use_adk = (selected == "adk") or (selected == "auto" and adk_adapter.is_available())
		if use_adk:
			async for evt in adk_adapter.execute_stream(payload.prompt):
				yield f"event: {evt.get('type','message')}\n" + f"data: {json.dumps(evt)}\n\n"
			return
		async for ev in execute_tasks_stream(tasks):
			data = {
				"id": ev.id,
				"type": ev.type,
				"message": ev.message,
				"run_id": ev.run_id,
				"timestamp": ev.timestamp,
				"task_id": ev.task_id,
				"data": ev.data,
			}
			yield f"event: {ev.type}\n" + f"data: {json.dumps(data)}\n\n"

	return StreamingResponse(event_generator(), media_type="text/event-stream")


class CancelRequest(BaseModel):
	run_id: str = Field(min_length=8)


@router.post("/cancel")
async def cancel(payload: CancelRequest) -> dict:
	success = registry.cancel(payload.run_id)
	return {"ok": success}


