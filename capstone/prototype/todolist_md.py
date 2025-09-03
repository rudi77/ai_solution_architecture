from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


def _slugify(name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    slug = (
        name.strip().lower().replace(" ", "-")
        .replace("/", "-").replace("\\", "-")
    )
    return "".join(ch for ch in slug if ch in allowed)


def get_todolist_path(session_id: Optional[str] = None, base_dir: str = "./checklists") -> Path:
    todolist_dir = Path(base_dir)
    todolist_dir.mkdir(parents=True, exist_ok=True)
    sid = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
    return todolist_dir / f"todolist_{sid}.md"


async def create_todolist_md(
    llm: Any,
    *,
    user_request: str,
    system_prompt: str,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """Generate a fresh Todo List as Markdown using the LLM and save it.

    Returns the file path as string.
    """
    prompt = f"""
You are a senior delivery engineer.
Create a concise, actionable Todo List as a pure Markdown checklist.

Rules:
- Output ONLY a checklist. No title, no meta, no notes, no explanations.
- Each line must be a checkbox item: "- [ ] <short task>".
- Use stable numeric prefixes like "1.", "2." inside the line to enable referencing tasks later.
- Keep items short, unambiguous, and implementation-oriented.

User Request:
{user_request}
""".strip()

    md = await llm.generate_response(prompt, system_prompt=system_prompt)

    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
    path.write_text(md, encoding="utf-8")
    return str(path)


async def update_todolist_md(
    llm: Any,
    *,
    instruction: str,
    system_prompt: str,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """Update an existing Todo List Markdown by providing an instruction.

    The function loads the current Markdown, asks the LLM to apply the change,
    and writes back the full updated Markdown. Returns the file path as string.
    """
    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
    if not path.exists():
        # If file does not exist yet, start with an empty list
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    current_md = path.read_text(encoding="utf-8")

    prompt = f"""
You are a precise editor of a Markdown checklist.
Apply the instruction to the checklist.

Rules:
- Return ONLY the full updated checklist (no comments, no code fences, no headings, no meta).
- Preserve existing task IDs and wording unless the instruction says otherwise.

Instruction: {instruction}

Current Checklist:
{current_md}
""".strip()

    updated_md = await llm.generate_response(prompt, system_prompt=system_prompt)

    # No meta handling; checklist-only by design

    path.write_text(updated_md, encoding="utf-8")
    return str(path)


# Optional backwards-compatibility aliases for one release
create_checklist_md = create_todolist_md  # type: ignore
update_checklist_md = update_todolist_md  # type: ignore
get_checklist_path = get_todolist_path  # type: ignore


