from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


# ---------- helpers ----------

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


def _ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


# ---------- public API (wrappers the agent expects) ----------

async def create_todolist_md(
    llm: Any,
    *,
    user_request: str,
    system_prompt: str,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """
    Erzeugt eine vollständige Todo-Liste (Markdown) mit den Sektionen:
    - Title
    - Meta (created/last-updated)
    - Tasks (Checkbox-Liste; JEDES ausführbare Item enthält im Text `tool: <exact_tool_name>`)
    - Open Questions (awaiting user)
    - Notes

    Rückgabe: Dateipfad als String.
    """
    guide = """
Create a concise, executable TODO plan in pure Markdown.

Sections (in this exact order):
1) # Todo List
2) ## Meta
   - created: <ISO8601>
   - last-updated: <ISO8601>
3) ## Tasks
   - [ ] <short task> (tool: <exact_tool_name>)  // each executable task includes 'tool: <...>'
   - Keep tasks atomic, verifiable, and implementation-oriented.
   - Prefer 3–10 tasks.
4) ## Open Questions (awaiting user)
   - Bullet list of clarifying questions that are nice-to-have (non-blocking).
   - If none, keep the section but leave it empty.
5) ## Notes
   - Free-form notes/results appended as the workflow progresses.
   - If none, keep the section but leave it empty.

Strict rules:
- Output ONLY Markdown (no code fences, no extra commentary).
- Keep wording short and unambiguous.
- DO NOT remove the section headings.
- If you are unsure about tools, still propose tasks; the agent will reconcile tools later.
    """.strip()

    prompt = f"{guide}\n\nContext/user request:\n{user_request}"
    md = await llm.generate_response(prompt, system_prompt=system_prompt)

    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
    _ensure_file(path)
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
    """
    Aktualisiert eine bestehende Todo-Liste anhand einer Anweisung.
    Beispiele für 'instruction':
      - "Find the task that corresponds to tool 'create_repository' and mark it IN_PROGRESS."
      - "Under 'Open Questions (awaiting user)', add these bullets: ... "
      - "Set task 3 status to COMPLETED. Record result: {...}"

    Rückgabe: Dateipfad als String.
    """
    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
    _ensure_file(path)
    current_md = path.read_text(encoding="utf-8")

    # Der Editor-Prompt hält die Struktur stabil und lässt Anweisungen gezielt anwenden.
    prompt = f"""
You are a precise editor of a structured Markdown TODO document.

Document shape MUST remain:
# Todo List
## Meta
- created: <ISO8601>
- last-updated: <ISO8601>
## Tasks
- [ ] ...
## Open Questions (awaiting user)
- ...
## Notes
- ...

Apply the instruction to the document.

Rules:
- Return ONLY the full updated Markdown (no comments, no code fences).
- Preserve existing sections and ordering.
- If a section is missing, recreate it with the correct heading.
- When modifying Tasks:
  - Keep checkbox format "- [ ]" or "- [x]" (we accept text status like IN_PROGRESS/COMPLETED as suffixes if requested),
  - Prefer to identify tasks by 'tool: <name>' or by stable numeric prefix if present.
- Update the 'last-updated' field in Meta to current ISO8601 (you can infer a plausible timestamp).
- Do not change 'created' value.

Instruction:
{instruction}

Current Document:
{current_md}
""".strip()

    updated_md = await llm.generate_response(prompt, system_prompt=system_prompt)

    path.write_text(updated_md, encoding="utf-8")
    return str(path)


# ---------- deterministic rendering from structured state ----------
def render_todolist_markdown(
    *,
    tasks: list[dict],
    open_questions: list[str] | None,
    session_id: Optional[str] = None,
    base_dir: str = "./checklists",
) -> str:
    """Render the Markdown Todo List from in-memory structured state.

    This function is the single renderer: it does not call the LLM and ensures
    the Markdown view is always consistent with the authoritative task state.

    Args:
        tasks: List of task dictionaries containing at least id, title, status, optional tool/params/notes.
        open_questions: Optional list of clarifying questions.
        session_id: Current session identifier used to determine the file path.
        base_dir: Directory to store Markdown files.

    Returns:
        The file path where the Markdown view was written.
    """
    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
    _ensure_file(path)

    created = datetime.now().isoformat()
    last_updated = datetime.now().isoformat()

    lines: list[str] = []
    lines.append("# Todo List")
    lines.append("## Meta")
    lines.append(f"- created: {created}")
    lines.append(f"- last-updated: {last_updated}")
    lines.append("## Tasks")

    def _checkbox(status: str) -> str:
        # Render checkbox based on status; text status retained for clarity
        checked = status.upper() in {"COMPLETED"}
        box = "[x]" if checked else "[ ]"
        return box

    for t in tasks:
        tid = str(t.get("id", ""))
        title = str(t.get("title", "")).strip() or tid
        status = str(t.get("status", "PENDING")).upper()
        tool = t.get("tool")
        params = t.get("params") or {}
        notes = str(t.get("notes", "")).strip()

        suffix_parts: list[str] = [f"status: {status}"]
        if tool:
            suffix_parts.append(f"tool: {tool}")
        if params:
            # keep params compact to avoid noisy Markdown
            suffix_parts.append(f"params: {params}")
        if notes:
            suffix_parts.append(f"notes: {notes}")
        suffix = " (" + ", ".join(suffix_parts) + ")" if suffix_parts else ""

        lines.append(f"- {_checkbox(status)} {title}{suffix}")

    lines.append("## Open Questions (awaiting user)")
    oq = open_questions or []
    if oq:
        for q in oq:
            lines.append(f"- {q}")
    lines.append("## Notes")

    md = "\n".join(lines) + "\n"
    path.write_text(md, encoding="utf-8")
    return str(path)


# ---------- backwards-compat (1 release grace) ----------

create_checklist_md = create_todolist_md  # type: ignore
update_checklist_md = update_todolist_md  # type: ignore
get_checklist_path = get_todolist_path    # type: ignore
