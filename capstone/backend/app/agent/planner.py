from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import re


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


