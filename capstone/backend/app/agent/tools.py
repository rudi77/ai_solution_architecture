from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class ToolResult:
	"""Result of a tool invocation."""
	status: str
	message: str
	data: Optional[Dict[str, Any]] = None


async def run_tool(tool: str, action: str, params: Optional[Dict[str, Any]] = None) -> ToolResult:
	"""Dispatch to a mock tool implementation.

	This mimics MCP-backed tools for demo purposes.
	"""
	key = (tool, action)
	if key == ("git", "create_repo"):
		name = (params or {}).get("repository_name", "new-repo")
		return ToolResult(status="ok", message=f"repository_created:{name}", data={"repository": name})
	if key == ("fs", "apply_templates"):
		template = (params or {}).get("template", "default")
		return ToolResult(status="ok", message=f"templates_applied:{template}", data={"template": template})
	if key == ("fs", "generate_tests"):
		return ToolResult(status="ok", message="tests_generated", data={})
	if key == ("ci", "setup_pipeline"):
		provider = (params or {}).get("provider", "github-actions")
		return ToolResult(status="ok", message=f"pipeline_configured:{provider}", data={"provider": provider})
	return ToolResult(status="skipped", message=f"no_such_tool:{tool}.{action}", data=params or {})


