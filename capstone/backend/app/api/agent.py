from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.planner import plan_service_creation, PlannedTask
from app.agent.executor import execute_tasks


router = APIRouter(prefix="/agent", tags=["agent"])


class ExecuteRequest(BaseModel):
	prompt: str = Field(min_length=3)


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


