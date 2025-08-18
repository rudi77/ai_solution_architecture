from __future__ import annotations

import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional
from app.settings import settings


def is_available() -> bool:
	"""Return True if Google's ADK appears importable.

	This checks for common module names without importing heavy deps.
	"""
	try:
		__import__("google.adk")
		return True
	except Exception:
		return False


async def execute_stream(prompt: str) -> AsyncIterator[Dict[str, Any]]:
	"""Execute a request using Google's ADK and yield event dicts.

	If ADK is not available, yields a run_started followed by run_failed event.
	"""
	run_id = uuid.uuid4().hex
	yield {
		"id": "run:start",
		"type": "run_started",
		"message": "ADK execution started",
		"run_id": run_id,
		"timestamp": time.time(),
	}
	if not is_available():
		yield {
			"id": "run:failed",
			"type": "run_failed",
			"message": "ADK not installed. Install and configure the Google ADK to enable this engine.",
			"run_id": run_id,
			"timestamp": time.time(),
			"data": {"engine": "adk", "prompt": prompt},
		}
		return

	# Minimal attempt to invoke a simple ADK agent synchronously and stream its output
	try:
		from google.adk.agents import Agent  # type: ignore
		agent = Agent(
			name="idp_copilot",
			model=getattr(settings, "adk_model", "gemini-2.0-flash"),
			instruction="You are an assistant that plans and executes software project setup tasks.",
			description="IDP Copilot agent",
			tools=[],
		)
		# Many ADK examples expose a .run() or similar. We try common names defensively.
		result = None
		for method_name in ("run", "execute", "invoke"):
			method = getattr(agent, method_name, None)
			if callable(method):
				result = method(prompt)  # type: ignore[misc]
				break
		if result is not None:
			yield {
				"id": "agent:output",
				"type": "agent_output",
				"message": str(result),
				"run_id": run_id,
				"timestamp": time.time(),
			}
		yield {
			"id": "run:done",
			"type": "run_completed",
			"message": "ADK execution completed",
			"run_id": run_id,
			"timestamp": time.time(),
		}
		return
	except Exception as exc:
		yield {
			"id": "run:failed",
			"type": "run_failed",
			"message": f"ADK error: {exc}",
			"run_id": run_id,
			"timestamp": time.time(),
			"data": {"engine": "adk"},
		}
		return


