from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import re
import json


@dataclass
class PlannedTask:
	id: str
	title: str
	status: str = "pending"


def detect_repository_name(text: str) -> Optional[str]:
	pattern = re.compile(r"\b([a-z][a-z0-9]+(?:[-_][a-z0-9]+)*)\b")
	for token in pattern.findall(text.lower()):
		if token not in {"service", "rest", "api", "bitte", "erstelle", "erzeuge", "neuen", "in", "go"}:
			return token
	return None


def plan_service_creation(
	user_text: str,
	repository_name: Optional[str] = None,
	language: Optional[str] = None,
	template: Optional[str] = None,
	ci_provider: Optional[str] = None,
) -> List[PlannedTask]:
	"""Create a minimal plan for service creation.

	Attempts to infer repository name if not provided; includes optional
	language, template, and CI provider hints in task titles.
	"""
	name = repository_name or detect_repository_name(user_text)
	tasks: List[PlannedTask] = []
	if name:
		tasks.append(PlannedTask(id="t1", title=f"Git Repo anlegen ({name})"))
	else:
		tasks.append(PlannedTask(id="t1", title="Repo-Name klären"))

	if template or language:
		hint_parts = []
		if template:
			hint_parts.append(template)
		if language:
			hint_parts.append(language)
		hint = ", ".join(hint_parts)
		tasks.append(PlannedTask(id="t2", title=f"Templates einfügen ({hint})"))
	else:
		tasks.append(PlannedTask(id="t2", title="Templates einfügen"))

	tasks.append(PlannedTask(id="t3", title="Unit Tests generieren"))

	if ci_provider:
		tasks.append(PlannedTask(id="t4", title=f"CI/CD Pipeline konfigurieren ({ci_provider})"))
	else:
		tasks.append(PlannedTask(id="t4", title="CI/CD Pipeline konfigurieren"))

	return tasks



def _adk_available() -> bool:
	try:
		__import__("google.adk")
		return True
	except Exception:
		return False


def generate_plan_with_agent(user_text: str) -> List[PlannedTask]:
	"""Use an LLM agent (ADK if available) to produce a plan from the prompt.

	Falls back to the deterministic plan if ADK is not available or parsing fails.
	"""
	if not _adk_available():
		return plan_service_creation(user_text)

	try:
		from google.adk.agents import Agent  # type: ignore

		system_instruction = (
			"You are a planning assistant. Read the user's request and return a concise step-by-step "
			"plan to create or modify a software service. Respond ONLY in JSON as an array named \"tasks\", "
			"where each item has a \"title\" string. Example: {\"tasks\":[{\"title\":\"Initialize git repo\"}]}"
		)
		agent = Agent(
			name="planner",
			model="gemini-2.0-flash",
			instruction=system_instruction,
			description="Planning agent",
			tools=[],
		)
		result = None
		for method_name in ("run", "execute", "invoke"):
			fn = getattr(agent, method_name, None)
			if callable(fn):
				result = fn(user_text)  # type: ignore[misc]
				break
		if result is None:
			return plan_service_creation(user_text)

		text = str(result)
		start = text.find("{")
		end = text.rfind("}")
		payload = text if start == -1 or end == -1 else text[start : end + 1]
		data = json.loads(payload)
		raw_tasks = data["tasks"] if isinstance(data, dict) and "tasks" in data else data
		titles = [t.get("title") if isinstance(t, dict) else str(t) for t in raw_tasks]
		titles = [t for t in titles if isinstance(t, str) and t.strip()]
		if not titles:
			return plan_service_creation(user_text)
		planned: List[PlannedTask] = []
		for idx, title in enumerate(titles, start=1):
			planned.append(PlannedTask(id=f"t{idx}", title=title.strip()))
		return planned
	except Exception:
		return plan_service_creation(user_text)


