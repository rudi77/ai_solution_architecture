from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Awaitable, Union
import asyncio
import concurrent.futures
import json


JsonDict = Dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    func: Callable[..., Union[JsonDict, Awaitable[JsonDict]]]
    is_async: bool = True
    timeout: Optional[float] = None
    aliases: Optional[List[str]] = None
    # Optional provider that returns an ExecutorCapabilities-like dict describing actions
    # This enables capability handshakes for sub-agents and tools.
    capabilities_provider: Optional[Callable[[], Dict[str, Any]]] = None


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def export_openai_tools(tools: List[ToolSpec]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def find_tool(tools: List[ToolSpec], name_or_alias: str) -> Optional[ToolSpec]:
    if not name_or_alias:
        return None
    target = _normalize(name_or_alias)
    for t in tools:
        if _normalize(t.name) == target:
            return t
        if t.aliases:
            for a in t.aliases:
                if _normalize(a) == target:
                    return t
    return None


async def execute_tool(tool: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if tool.is_async or asyncio.iscoroutinefunction(tool.func):
            coro = tool.func(**params)  # type: ignore[misc]
            if not asyncio.iscoroutine(coro):
                # In case is_async was set but func isn't actually async
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, lambda: tool.func(**params))  # type: ignore[misc]
                    if tool.timeout:
                        result = await asyncio.wait_for(future, timeout=tool.timeout)
                    else:
                        result = await future
            else:
                if tool.timeout:
                    result = await asyncio.wait_for(coro, timeout=tool.timeout)
                else:
                    result = await coro
        else:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = loop.run_in_executor(executor, lambda: tool.func(**params))  # type: ignore[misc]
                if tool.timeout:
                    result = await asyncio.wait_for(future, timeout=tool.timeout)
                else:
                    result = await future

        if isinstance(result, dict):
            return result
        return {"success": True, "result": result}
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Tool '{tool.name}' timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_tool_by_name(tools: List[ToolSpec], name_or_alias: str, params: Dict[str, Any]) -> Dict[str, Any]:
    spec = find_tool(tools, name_or_alias)
    if not spec:
        return {"success": False, "error": f"Tool '{name_or_alias}' not found"}
    return await execute_tool(spec, params)


# === Lookup index helpers ===
def build_tool_index(tools: List[ToolSpec]) -> Dict[str, ToolSpec]:
    """Create a lookup index for tools and their aliases using normalized keys.

    Keys normalize hyphens/whitespace and case to ensure consistent resolution.
    """
    index: Dict[str, ToolSpec] = {}
    for tool in tools:
        index[_normalize(tool.name)] = tool
        if tool.aliases:
            for alias in tool.aliases:
                index[_normalize(alias)] = tool
    return index


async def execute_tool_by_name_from_index(index: Dict[str, ToolSpec], name_or_alias: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool resolved via a prebuilt index. Returns a standard result dict."""
    if not name_or_alias:
        return {"success": False, "error": "Tool name is empty"}
    spec = index.get(_normalize(name_or_alias))
    if not spec:
        return {"success": False, "error": f"Tool '{name_or_alias}' not found"}
    # Best-effort param sanitization: ensure JSON-serializable
    try:
        json.dumps(params)
    except Exception:
        params = {k: str(v) for k, v in (params or {}).items()}
    return await execute_tool(spec, params)


def merge_tool_specs(*tool_groups: List[ToolSpec]) -> List[ToolSpec]:
    """Merge multiple tool lists by normalized name, last one wins.

    This allows composing BUILTIN_TOOLS with agent-tools without duplicates.
    """
    merged: Dict[str, ToolSpec] = {}
    for group in tool_groups:
        for t in group or []:
            merged[_normalize(t.name)] = t
    return list(merged.values())

