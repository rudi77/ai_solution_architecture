from __future__ import annotations

from typing import Any, Dict, List

from capstone.prototype.tools_builtin import ALL_TOOLS_WITH_AGENTS
from capstone.prototype.tools import ToolSpec, build_tool_index
from capstone.prototype.agent import ReActAgent
from capstone.prototype.llm_provider import OpenAIProvider  # type: ignore[attr-defined]
from ..config import get_openai_api_key


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _resolve_tools(allowed: List[str] | None) -> List[ToolSpec]:
    names = set(_normalize(x) for x in (allowed or []))
    out: List[ToolSpec] = []
    for t in ALL_TOOLS_WITH_AGENTS:
        if not names or _normalize(t.name) in names or any(_normalize(a) in names for a in (t.aliases or [])):
            out.append(t)
    return out


def build_agent_system_from_yaml(doc: Dict[str, Any]) -> Dict[str, Any]:
    system = doc.get("system", {})
    agents_cfg = doc.get("agents", [])

    # If there is exactly one agent, build single-agent instance directly (no orchestrator)
    if isinstance(agents_cfg, list) and len(agents_cfg) == 1:
        single_cfg = agents_cfg[0]
        agent = _build_agent(single_cfg)
        # Ensure tool indices and prompts are initialized
        try:
            agent.tool_index = build_tool_index(agent.tools)
            agent.final_system_prompt = agent._build_final_system_prompt()
            agent.executor_index = agent._build_executor_index()
        except Exception:
            pass
        return {
            "system": system,
            "agents": {single_cfg.get("id", "agent"): single_cfg},
            "instance": agent,
        }

    # Multi-agent legacy mode: try orchestrator + sub-agents composition if defined
    sub_agents: Dict[str, ReActAgent] = {}
    orchestrator_cfg = None
    for a in agents_cfg:
        if str(a.get("role", "")).lower() == "orchestrator":
            orchestrator_cfg = a
        else:
            sub_agents[a["id"]] = _build_agent(a)

    # If no orchestrator provided, but multiple agents exist, pick the first as primary (single-agent fallback)
    if orchestrator_cfg is None and agents_cfg:
        primary = agents_cfg[0]
        agent = _build_agent(primary)
        try:
            agent.tool_index = build_tool_index(agent.tools)
            agent.final_system_prompt = agent._build_final_system_prompt()
            agent.executor_index = agent._build_executor_index()
        except Exception:
            pass
        return {
            "system": system,
            "agents": {primary.get("id", "agent"): primary},
            "instance": agent,
        }

    if orchestrator_cfg is None:
        raise ValueError("no agents defined")

    orchestrator = _build_agent(orchestrator_cfg)

    # Attach sub-agents as tools where referenced by allow list
    allow = (orchestrator_cfg.get("tools") or {}).get("allow") or []
    for sub_id, sub in sub_agents.items():
        if sub_id in allow or _normalize(sub_id) in {_normalize(x) for x in allow}:
            orchestrator.tools.append(
                sub.to_tool(
                    name=sub_id,
                    description=sub_id,
                    allowed_tools=[t.name for t in sub.tools],
                    budget={"max_steps": sub.max_steps},
                    mission_override=sub.mission_text or None,
                )
            )

    # Rebuild tool index, prompt, and executor capabilities now that tools are attached
    try:
        orchestrator.tool_index = build_tool_index(orchestrator.tools)
        orchestrator.final_system_prompt = orchestrator._build_final_system_prompt()
        orchestrator.executor_index = orchestrator._build_executor_index()
        try:
            orchestrator.logger.info(
                "final_system_prompt",
                mode="compose",
                prompt=orchestrator.final_system_prompt,
            )
        except Exception:
            pass
    except Exception:
        pass

    return {
        "system": system,
        "agents": {
            "orchestrator": orchestrator_cfg.get("id"),
            **{k: v for k, v in ((a.get("id"), a) for a in agents_cfg if a.get("id"))},
        },
        "instance": orchestrator,
    }


def _build_agent(cfg: Dict[str, Any]) -> ReActAgent:
    model = (cfg.get("model") or cfg.get("default_model") or {})
    provider = str(model.get("provider") or "openai").lower()
    if provider != "openai":
        raise ValueError("Only openai provider supported in v1")
    api_key = get_openai_api_key()
    llm = OpenAIProvider(api_key=api_key, model=str(model.get("model") or "gpt-4.1"), temperature=float(model.get("temperature", 0.1)))

    allow = (cfg.get("tools") or {}).get("allow") or []
    tools = _resolve_tools(allow)
    return ReActAgent(
        system_prompt=str(cfg.get("system_prompt") or ""),
        llm=llm,
        tools=tools,
        max_steps=int(cfg.get("max_steps", 50)),
        mission=str(cfg.get("mission") or ""),
    )


