from __future__ import annotations

import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional
from app.settings import settings
import os


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
		# Optional MCP tools wiring
		tools_list = []
		if getattr(settings, "mcp_enable", False):
			try:
				from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, SseServerParams  # type: ignore
				stdio_servers = []
				# Filesystem MCP server via npx if directory is provided
				fs_dir = getattr(settings, "mcp_filesystem_dir", None)
				if fs_dir:
					stdio_servers.append(
						MCPToolset(
							connection_params=StdioServerParameters(command="npx", args=[
								"@modelcontextprotocol/server-filesystem",
								"--root",
								fs_dir,
							]),
						)
					)
				# Additional stdio servers from JSON env (array of specs)
				import json as _json
				stdio_json = getattr(settings, "mcp_stdio_json", None)
				if stdio_json:
					for spec in _json.loads(stdio_json):
						cmd = spec.get("command")
						args = spec.get("args", [])
						if cmd:
							stdio_servers.append(MCPToolset(connection_params=StdioServerParameters(command=cmd, args=args)))
				# Optional SSE server from env MCP_SSE_URL
				sse_url = os.getenv("MCP_SSE_URL")
				if sse_url:
					stdio_servers.append(MCPToolset(connection_params=SseServerParams(url=sse_url)))
				# Extend tools_list with all discovered MCP toolsets
				tools_list.extend(stdio_servers)
			except Exception:
				# If MCP wiring fails, continue without tools
				pass

		agent = Agent(
			name="idp_copilot",
			model=getattr(settings, "adk_model", "gemini-2.0-flash"),
			instruction="You are an assistant that plans and executes software project setup tasks.",
			description="IDP Copilot agent",
			tools=tools_list,
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


