from __future__ import annotations

from fastapi import APIRouter

from capstone.prototype.tools_builtin import BUILTIN_TOOLS
from capstone.prototype.tools import export_openai_tools


router = APIRouter()


@router.get("/tools")
async def list_tools() -> dict:
    tools = export_openai_tools(BUILTIN_TOOLS)
    # Normalize to a concise schema for UI consumption
    items = []
    for t in tools:
        fn = t.get("function", {})
        items.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description"),
                "parameters": fn.get("parameters"),
            }
        )
    return {"tools": items}


