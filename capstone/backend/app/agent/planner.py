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


def plan_service_creation(user_text: str, repository_name: Optional[str] = None) -> List[PlannedTask]:
	# Minimal, static plan with name detection
	name = repository_name or detect_repository_name(user_text)
	return [
		PlannedTask(id="t1", title=f"Git Repo anlegen{f' ({name})' if name else ''}" if name else "Repo-Name klären"),
		PlannedTask(id="t2", title="Templates einfügen"),
		PlannedTask(id="t3", title="Unit Tests generieren"),
		PlannedTask(id="t4", title="CI/CD Pipeline konfigurieren"),
	]


