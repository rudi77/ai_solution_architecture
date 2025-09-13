"""Built-in tools for the IDP Copilot.

This module provides a clean interface to all available tool packages
without any fallback code or legacy implementations.
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List
import structlog

from .tools import ToolSpec, merge_tool_specs
from .agent import ReActAgent
from .llm_provider import LLMProvider

# Import all tool packages
from .tool_packages.git_tools import GIT_TOOLS
from .tool_packages.project_tools import PROJECT_TOOLS
from .tool_packages.cicd_tools import CICD_TOOLS
from .tool_packages.k8s_tools import K8S_TOOLS
from .tool_packages.docs_tools import DOCS_TOOLS
from .tool_packages.file_tools import FILE_TOOLS

logger = structlog.get_logger()


# ==== Sub-Agent Wrapper as Tool ====
async def run_sub_agent(
    *,
    task: str,
    inputs: Dict[str, Any] | None = None,
    shared_context: Dict[str, Any] | None = None,
    allowed_tools: List[str] | None = None,
    budget: Dict[str, Any] | None = None,
    resume_token: str | None = None,
    answers: Dict[str, Any] | None = None,
    agent_name: str | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run a constrained sub-agent and return either a patch or need_user_input.

    This wrapper expects the hosting orchestrator to pass in the orchestrator's LLMProvider via kwargs['llm']
    and the base system prompt via kwargs['system_prompt'] for consistency.
    """
    llm: LLMProvider | None = kwargs.get("llm")
    system_prompt: str = kwargs.get("system_prompt") or ""
    if llm is None:
        return {"success": False, "error": "Missing llm provider for sub-agent"}

    # Construct tool whitelist index from BUILTIN_TOOLS
    allow = [t for t in BUILTIN_TOOLS if (not allowed_tools) or (t.name in allowed_tools)]
    subagent = ReActAgent(system_prompt=None, llm=llm, tools=allow, max_steps=int((budget or {}).get("max_steps", 12)), mission=system_prompt)

    # Seed minimal context (ephemeral + child-session) to avoid state collision
    parent_sid = (shared_context or {}).get("session_id") or "no-session"
    subagent.session_id = f"{parent_sid}:sub:{(agent_name or 'subagent')}"
    subagent.context = {
        "user_request": task,
        "known_answers_text": (shared_context or {}).get("known_answers_text", ""),
        "facts": (shared_context or {}).get("facts", {}),
        "version": int((shared_context or {}).get("version", 1)),
        "suppress_markdown": True,
        "ephemeral_state": True,
        # tag for logging and ownership
        "agent_name": agent_name or "subagent",
    }

    # Run a short loop
    transcript: List[str] = []
    async for chunk in subagent.process_request(task, session_id=subagent.session_id):
        transcript.append(chunk)

    # Inspect sub-agent state
    if subagent.context.get("awaiting_user_input"):
        return {
            "success": False,
            "need_user_input": subagent.context.get("awaiting_user_input"),
            "state_token": "opaque",  # kept simple for v1
        }

    # Build a minimal patch reflecting only status updates against master tasks
    patch = {
        "base_version": int((shared_context or {}).get("version", 1)),
        "agent_name": agent_name or "subagent",
        "ops": []
    }
    master_tasks = list((shared_context or {}).get("tasks", []))
    target_task_id = str((shared_context or {}).get("target_task_id") or "").strip() or None
    wrapper_norm = (agent_name or "subagent").strip().lower().replace("-", "_").replace(" ", "_")
    def _norm(s: str) -> str:
        return (s or "").strip().lower().replace("-", "_").replace(" ", "_")
    def _find_master_task_id_by_tool(tool_name: str) -> str | None:
        # 0) Deterministic: prefer explicitly given target_task_id
        if target_task_id:
            return target_task_id
        norm = _norm(tool_name)
        # 1) Direct tool match
        for mt in master_tasks:
            tt = _norm(mt.get("tool"))
            if tt and tt == norm:
                return str(mt.get("id"))
        # 2) Prefixed tool match: wrapper.action
        for mt in master_tasks:
            tt = _norm(mt.get("tool"))
            if tt and tt == f"{wrapper_norm}.{norm}":
                return str(mt.get("id"))
        # 3) Fallback: match by executor_id + action
        for mt in master_tasks:
            exec_id = _norm(mt.get("executor_id"))
            action = _norm(mt.get("action"))
            if action == norm and (not exec_id or exec_id == wrapper_norm):
                return str(mt.get("id"))
        return None
    for t in subagent.context.get("tasks", []):
        status = str(t.get("status","")).upper()
        tool_name = t.get("tool")
        if tool_name and status in {"IN_PROGRESS","COMPLETED"}:
            tid = _find_master_task_id_by_tool(tool_name)
            if tid:
                patch["ops"].append({"op":"update","task_id":tid,"fields":{"status":status}})

    return {"success": True, "patch": patch, "result": {"transcript": "".join(transcript)}}


# ==== Tool Collections ====

# Merge all tool packages into unified collections
BUILTIN_TOOLS: List[ToolSpec] = merge_tool_specs(
    GIT_TOOLS,
    PROJECT_TOOLS, 
    CICD_TOOLS,
    K8S_TOOLS,
    DOCS_TOOLS,
    FILE_TOOLS,
)

# Simplified tool set for basic operations
BUILTIN_TOOLS_SIMPLIFIED: List[ToolSpec] = merge_tool_specs(
    GIT_TOOLS[:1],  # Just create_repository
    PROJECT_TOOLS[:1],  # Just validate_project_name_and_type
)

# Sub-agent tools
AGENT_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="agent_scaffold_webservice",
        description="Sub-agent: scaffolds a webservice using whitelisted tools",
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "inputs": {"type": "object"},
                "shared_context": {"type": "object"},
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
                "budget": {"type": "object"},
                "resume_token": {"type": "string"},
                "answers": {"type": "object"},
            },
            "required": ["task"],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=run_sub_agent,
        is_async=True,
        timeout=120,
        aliases=["agent_scaffold", "agent_webservice"],
    )
]

# Export unified tool collections
ALL_TOOLS: List[ToolSpec] = BUILTIN_TOOLS
ALL_TOOLS_WITH_AGENTS: List[ToolSpec] = merge_tool_specs(BUILTIN_TOOLS, AGENT_TOOLS)