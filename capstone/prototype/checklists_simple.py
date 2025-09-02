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


def get_checklist_path(project_name: str, session_id: Optional[str] = None, base_dir: str = "./checklists") -> Path:
    checklist_dir = Path(base_dir)
    checklist_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(project_name) or "project"
    sid = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
    return checklist_dir / f"{slug}_{sid}.md"


async def create_checklist_md(
    llm: Any,
    *,
    project_name: str,
    project_type: str,
    user_request: str,
    requirements: Dict[str, Any],
    system_prompt: str,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """Generate a fresh checklist as Markdown using the LLM and save it.

    Returns the file path as string.
    """
    prompt = f"""
You are a senior delivery engineer.
Create a concise, actionable project implementation checklist in Markdown.

Constraints:
- Output ONLY the final Markdown, no explanations.
- Use simple sections: title, meta (created, last-updated), tasks, notes.
- Tasks: use checkbox list (- [ ]), stable numeric IDs and short descriptions.
- Keep it self-contained so it can be updated by future prompts.

Context:
- Project Name: {project_name}
- Project Type: {project_type}
- User Request: {user_request}
- Requirements: {requirements}
""".strip()

    md = await llm.generate_response(prompt, system_prompt=system_prompt)

    path = get_checklist_path(project_name, session_id=session_id, base_dir=base_dir)
    path.write_text(md, encoding="utf-8")
    return str(path)


async def update_checklist_md(
    llm: Any,
    *,
    project_name: str,
    instruction: str,
    system_prompt: str,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """Update an existing checklist Markdown by providing an instruction.

    The function loads the current Markdown, asks the LLM to apply the change,
    and writes back the full updated Markdown. Returns the file path as string.
    """
    path = get_checklist_path(project_name, session_id=session_id, base_dir=base_dir)
    if not path.exists():
        # If file does not exist yet, create a minimal shell to update
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Checklist: {project_name}\n\n- Meta: Created: {datetime.now().isoformat()}\n\n## Tasks\n", encoding="utf-8")

    current_md = path.read_text(encoding="utf-8")

    prompt = f"""
You are a precise editor of a Markdown checklist.
Update the given checklist according to the instruction.

Rules:
- Return ONLY the complete updated Markdown (no comments, no code fences).
- Preserve the existing structure, IDs, and prior content unless the instruction says otherwise.
- Update the meta 'Last-Updated' timestamp to the current time in ISO format.

Instruction: {instruction}

Current Checklist Markdown:
{current_md}
""".strip()

    updated_md = await llm.generate_response(prompt, system_prompt=system_prompt)

    # Best-effort meta update if the model did not include it
    try:
        if "Last-Updated" not in updated_md:
            stamp = datetime.now().isoformat()
            lines = updated_md.splitlines()
            injected = False
            for i, line in enumerate(lines):
                if line.strip().lower().startswith("- meta:"):
                    lines[i] = f"- Meta: Last-Updated: {stamp}"
                    injected = True
                    break
            if not injected:
                lines.insert(1, f"- Meta: Last-Updated: {stamp}")
            updated_md = "\n".join(lines)
    except Exception:
        pass

    path.write_text(updated_md, encoding="utf-8")
    return str(path)


