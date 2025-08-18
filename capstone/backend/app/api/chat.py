from typing import List, Literal, Optional
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.agent.planner import plan_service_creation, generate_plan_with_agent


router = APIRouter(prefix="/chat", tags=["chat"])


Role = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
	role: Role
	content: str = Field(min_length=1)


class ChatRequest(BaseModel):
	messages: List[ChatMessage]


class PlannedTaskModel(BaseModel):
	id: str
	title: str
	status: str


class ChatResponse(BaseModel):
	reply: str
	clarification_needed: bool = False
	missing_fields: Optional[List[str]] = None
	tasks: Optional[List[PlannedTaskModel]] = None
	fields: Optional[dict] = None


_REPO_NAME_RE = re.compile(r"\b[a-z0-9]+(?:[-_][a-z0-9]+)*\b")


def _needs_repo_name_clarification(text: str) -> bool:
	lowered = text.lower()
	mentions_service = any(w in lowered for w in ["service", "rest", "api"]) and any(
		w in lowered for w in ["erzeuge", "erstelle", "create", "generate"]
	)
	if not mentions_service:
		return False
	# Heuristic: consider that a repo name-like token exists
	possible = _REPO_NAME_RE.findall(lowered)
	if not possible:
		return True
	# Common phrases without actual names
	noise = {"service", "rest", "api", "einen", "neuen", "bitte", "ein", "projekt"}
	return all(token in noise for token in possible)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
	last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
	if last_user is None:
		return ChatResponse(
			reply="Bitte gib eine Anweisung ein.",
			clarification_needed=False,
		)

	text = last_user.content.strip()
	missing: List[str] = []
	fields: dict = {}

	# Repo name clarification
	if _needs_repo_name_clarification(text):
		missing.append("repository_name")
	else:
		fields["repository_name"] = None

	# Language
	if not any(lang in text.lower() for lang in ["go", "python", "java", "typescript", "node", "rust"]):
		missing.append("language")

	# Template
	if "template" not in text.lower():
		missing.append("template")

	# CI provider
	if not any(ci in text.lower() for ci in ["github actions", "gitlab ci", "azure pipelines", "circleci"]):
		missing.append("ci_provider")

	if missing:
		return ChatResponse(
			reply="Bitte bestätige bzw. gib die fehlenden Angaben an: repo-name, language, template, ci-provider.",
			clarification_needed=True,
			missing_fields=missing,
			fields=fields or None,
		)

	# Prefer agent-based planning; it falls back to a deterministic plan if ADK is unavailable
	tasks = generate_plan_with_agent(text)
	return ChatResponse(
		reply="Ich habe eine Taskliste für die Service-Erstellung geplant.",
		clarification_needed=False,
		tasks=[PlannedTaskModel(id=t.id, title=t.title, status=t.status) for t in tasks],
		fields=fields or None,
	)


