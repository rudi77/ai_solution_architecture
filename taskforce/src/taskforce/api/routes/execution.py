import json
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from taskforce.application.executor import AgentExecutor

router = APIRouter()
executor = AgentExecutor()


class ExecuteMissionRequest(BaseModel):
    """Request to execute a mission."""
    mission: str
    profile: str = "dev"
    session_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    """Optional conversation history for chat integration.

    Format: List of message dictionaries with 'role' and 'content' keys.
    Example: [
        {"role": "user", "content": "Previous user message"},
        {"role": "assistant", "content": "Previous assistant response"}
    ]
    """
    # User context for RAG security filtering
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    scope: Optional[str] = None
    # LeanAgent flag (native tool calling, PlannerTool)
    lean: bool = False


class ExecuteMissionResponse(BaseModel):
    """Response from mission execution."""
    session_id: str
    status: str
    message: str


@router.post("/execute", response_model=ExecuteMissionResponse)
async def execute_mission(request: ExecuteMissionRequest):
    """Execute agent mission synchronously.

    Set `lean: true` to use LeanAgent with native tool calling.
    """
    try:
        # Build user_context if any RAG parameters provided
        user_context = None
        if request.user_id or request.org_id or request.scope:
            user_context = {
                "user_id": request.user_id,
                "org_id": request.org_id,
                "scope": request.scope,
            }

        result = await executor.execute_mission(
            mission=request.mission,
            profile=request.profile,
            session_id=request.session_id,
            conversation_history=request.conversation_history,
            user_context=user_context,
            use_lean_agent=request.lean,
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
    """Execute agent mission with streaming progress via SSE.

    Set `lean: true` to use LeanAgent with native tool calling.
    """
    # Build user_context if any RAG parameters provided
    user_context = None
    if request.user_id or request.org_id or request.scope:
        user_context = {
            "user_id": request.user_id,
            "org_id": request.org_id,
            "scope": request.scope,
        }

    async def event_generator():
        async for update in executor.execute_mission_streaming(
            mission=request.mission,
            profile=request.profile,
            session_id=request.session_id,
            conversation_history=request.conversation_history,
            user_context=user_context,
            use_lean_agent=request.lean,
        ):
            # Serialize dataclass to JSON, handling datetime
            data = json.dumps(asdict(update), default=str)
            yield f"data: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
