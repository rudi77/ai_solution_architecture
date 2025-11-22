import json
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from taskforce.application.executor import AgentExecutor

router = APIRouter()
executor = AgentExecutor()

class ExecuteMissionRequest(BaseModel):
    """Request to execute a mission."""
    mission: str
    profile: str = "dev"
    session_id: Optional[str] = None

class ExecuteMissionResponse(BaseModel):
    """Response from mission execution."""
    session_id: str
    status: str
    message: str

@router.post("/execute", response_model=ExecuteMissionResponse)
async def execute_mission(request: ExecuteMissionRequest):
    """Execute agent mission synchronously."""
    try:
        result = await executor.execute_mission(
            mission=request.mission,
            profile=request.profile,
            session_id=request.session_id
        )
        
        return ExecuteMissionResponse(
            session_id=result.session_id,
            status=result.status,
            message=result.final_message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute/stream")
async def execute_mission_stream(request: ExecuteMissionRequest):
    """Execute agent mission with streaming progress via SSE."""
    
    async def event_generator():
        async for update in executor.execute_mission_streaming(
            mission=request.mission,
            profile=request.profile,
            session_id=request.session_id
        ):
            # Serialize dataclass to JSON, handling datetime
            data = json.dumps(asdict(update), default=str)
            yield f"data: {data}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

