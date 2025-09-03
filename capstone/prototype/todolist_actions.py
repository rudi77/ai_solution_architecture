from __future__ import annotations

from typing import Any, Dict, Optional, Callable, Awaitable


# Prefer todolist helpers; aliases exist elsewhere for checklist compatibility
try:  # pragma: no cover - import shim
    from .todolist_md import create_todolist_md, update_todolist_md  # type: ignore
except Exception:  # pragma: no cover - runtime import fallback
    from todolist_md import create_todolist_md, update_todolist_md  # type: ignore


def normalize_todolist_action_name(action_name: str) -> str:
    """Normalize common LLM variants to canonical todolist action names.

    Returns the normalized action name (e.g., "create_todolist").
    """
    normalized = action_name.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in (
        "create_todolist",
        "create_checklist",
        "create_microservice_checklist",
        "create_a_microservice_checklist",
    ):
        return "create_todolist"
    return normalized


async def create_todolist(
    *,
    llm: Any,
    context: Dict[str, Any],
    system_prompt: str,
    session_id: Optional[str],
    logger: Any,
) -> str:
    """Create a Todo List using the Markdown helper and update the agent context.

    Best-effort fallback is attempted on failure; context keys remain
    backward-compatible (both todolist_* and checklist_* are maintained).
    """
    # Derive generic project info from context/user request to keep agent generic
    user_request = context.get("user_request", "") or ""
    # Simple slug from request
    try:
        lower = str(user_request).strip().lower()
        filtered = "".join(ch if (ch.isalnum() or ch in {" ", "-"}) else " " for ch in lower)
        words = [w for w in filtered.split() if w]
        project_name = "-".join(words[:6]) or "project"
    except Exception:
        project_name = "project"
    project_type = "generic"
    requirements: Dict[str, Any] = {}
    try:
        filepath = await create_todolist_md(
            llm,
            user_request=user_request,
            system_prompt=system_prompt,
            session_id=session_id,
        )
        context["todolist_created"] = True
        context["todolist_file"] = filepath
        # Back-compat keys
        context["checklist_created"] = True
        context["checklist_file"] = filepath
        # No project metadata in checklist-only mode
        return f"Created Todo List (saved to {filepath})"

    except Exception as e:
        logger.error("todolist_creation_failed", error=str(e))
        try:
            filepath = await create_todolist_md(
                llm,
                user_request=user_request,
                system_prompt=system_prompt,
                session_id=session_id,
            )
            context["todolist_created"] = True
            context["todolist_file"] = filepath
            context["checklist_created"] = True
            context["checklist_file"] = filepath
            return f"Created minimal Todo List (saved to {filepath}). Original error: {e}"
        except Exception as inner_e:
            logger.error("todolist_fallback_failed", error=str(inner_e))
            return f"Failed to create Todo List: {e}"


async def update_item_status(
    *,
    llm: Any,
    context: Dict[str, Any],
    system_prompt: str,
    session_id: Optional[str],
    parameters: Dict[str, Any],
) -> str:
    """Update a specific item in the Todo List via the Markdown helper.

    Expected parameters: item_id, status, notes (optional), result (optional).
    """
    # Checklist-only mode does not require project name; all ops are session-based

    item_id = parameters.get("item_id")
    status_text = parameters.get("status")
    notes = parameters.get("notes")
    result_txt = parameters.get("result")

    instruction_parts = [f"Set task {item_id} status to {status_text}."]
    if notes:
        instruction_parts.append(f"Add note to task {item_id}: {notes}.")
    if result_txt:
        instruction_parts.append(f"Record result for task {item_id}: {result_txt}.")
    instruction = " ".join(instruction_parts)

    filepath = await update_todolist_md(
        llm,
        instruction=instruction,
        system_prompt=system_prompt,
        session_id=session_id,
    )
    context["todolist_file"] = filepath
    # Back-compat key
    context["checklist_file"] = filepath
    return f"Updated Todo List (saved to {filepath})"


def get_next_executable_item(*, context: Dict[str, Any]) -> str:
    """Return a guidance message to open the current Todo List file."""
    path = context.get("todolist_file") or context.get("checklist_file")
    return f"Open and follow the Todo List: {path}" if path else "No Todo List created"


