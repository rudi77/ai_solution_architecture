from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.1


class AgentConfig(BaseModel):
    id: str
    role: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    mission: Optional[str] = None
    max_steps: int = 50
    tools: Dict[str, List[str]] | None = None  # {allow: [..]}
    model: Optional[ModelConfig] = None


class AgentSystem(BaseModel):
    version: int
    system: Dict[str, Any] = {}
    agents: List[AgentConfig]


