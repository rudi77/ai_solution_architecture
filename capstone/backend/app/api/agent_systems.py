from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.registry import AgentSystemRegistry
from ..core.builder import build_agent_system_from_yaml
from ..config import get_openai_api_key
from ..schemas.agent_system import AgentSystem


router = APIRouter()
registry = AgentSystemRegistry()


class RegisterResponse(BaseModel):
    id: str


@router.post("/agent-systems", response_model=RegisterResponse, status_code=201)
async def register_agent_system(doc: AgentSystem) -> RegisterResponse:
    try:
        _ = get_openai_api_key()
        resolved = build_agent_system_from_yaml(doc.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    system_id = str(doc.system.get("name") or doc.system.get("id") or uuid.uuid4())

    def _factory():
        # Build fresh instance each time
        return build_agent_system_from_yaml(doc.model_dump())["instance"]

    registry.register(system_id, _factory, {"config": doc.model_dump(), "resolved": {"agents": resolved["agents"]}})
    return RegisterResponse(id=system_id)


@router.get("/agent-systems/{system_id}")
async def get_agent_system(system_id: str) -> dict:
    res = registry.get_resolved(system_id)
    if not res:
        raise HTTPException(status_code=404, detail="not found")
    return res


