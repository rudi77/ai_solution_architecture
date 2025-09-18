from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Iterable, List, Tuple
import re
import litellm
import json
import uuid

from dataclasses import dataclass, field, asdict

# ===== Structured Plan Models (Single Source of Truth) =====
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def parse_task_status(value: Any) -> TaskStatus:
    """Parse arbitrary status strings to TaskStatus with safe fallbacks.

    Accepts common aliases like "open" -> PENDING, "inprogress" -> IN_PROGRESS, etc.
    """
    text = str(value or "").strip().replace("-", "_").replace(" ", "_").upper()
    if not text:
        return TaskStatus.PENDING

    alias = {
        "OPEN": "PENDING",
        "TODO": "PENDING",
        "INPROGRESS": "IN_PROGRESS",
        "DONE": "COMPLETED",
        "COMPLETE": "COMPLETED",
        "FAIL": "FAILED",
    }
    normalized = alias.get(text, text)
    try:
        return TaskStatus[normalized]
    except KeyError:
        return TaskStatus.PENDING


@dataclass
class TodoItem:
    position: int
    description: str
    tool: str
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING

    def to_json(self) -> str:
        """Serialize the TodoItem to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the TodoItem to a serializable dict."""
        return {
            "position": self.position,
            "description": self.description,
            "tool": self.tool,
            "parameters": self.parameters,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
        }

@dataclass
class TodoList:
    items: List[TodoItem]
    open_questions: List[str]
    notes: str
    todolist_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @staticmethod
    def from_json(json_text: Any) -> "TodoList":
        """Create a TodoList from an LLM JSON string/object.

        Accepts either a JSON string or a pre-parsed dict and returns
        a populated TodoList instance with sane fallbacks.
        """
        try:
            data = json.loads(json_text) if isinstance(json_text, str) else (json_text or {})
        except Exception:
            data = {}

        raw_items = data.get("items", []) or []
        items: List[TodoItem] = []
        for index, raw in enumerate(raw_items, start=1):
            try:
                position = int(raw.get("position", index))
            except Exception:
                position = index

            item = TodoItem(
                position=position,
                description=str(raw.get("description", "")).strip(),
                tool=str(raw.get("tool", "")).strip(),
                parameters=raw.get("parameters") or {},
                status=parse_task_status(raw.get("status")),
            )
            items.append(item)

        open_questions = [str(q) for q in (data.get("open_questions", []) or [])]
        notes = str(data.get("notes", ""))
        todolist_id = str(data.get("todolist_id") or str(uuid.uuid4()))

        return TodoList(todolist_id=todolist_id, items=items, open_questions=open_questions, notes=notes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TodoList to a serializable dict."""
        # Convert Enum to value for JSON friendliness
        def serialize_item(item: TodoItem) -> Dict[str, Any]:
            return {
                "position": item.position,
                "description": item.description,
                "tool": item.tool,
                "parameters": item.parameters,
                "status": item.status.value if isinstance(item.status, TaskStatus) else str(item.status),
            }

        return {
            "todolist_id": self.todolist_id,
            "items": [serialize_item(i) for i in self.items],
            "open_questions": list(self.open_questions or []),
            "notes": self.notes or "",
        }

    def to_json(self) -> str:
        """Serialize the TodoList to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        """
        Converts a todolist to a markdown string.
        """
        def _status_str(s: Any) -> str:
            # Normalize TaskStatus or string to lowercase text
            if hasattr(s, "value"):
                s = s.value  # Enum-like (e.g., TaskStatus)
            return str(s or "").strip()

        def _is_checked(status_text: str) -> bool:
            st = status_text.lower()
            # Treat these as completed
            return st in {"done", "completed", "success", "succeeded"}

        # Build markdown lines
        lines: List[str] = []
        title = f"Todo List — {self.todolist_id}"
        lines.append(f"# {title}\n")

        if (self.notes or "").strip():
            lines.append("## Notes")
            lines.append(self.notes.strip() + "\n")

        # Items
        lines.append("## Items")
        if not self.items:
            lines.append("_No items yet._\n")
        else:
            # Ensure stable ordering
            items_sorted = sorted(self.items, key=lambda i: (i.position, i.description or ""))
            for item in items_sorted:
                status_text = _status_str(item.status)
                checked = "x" if _is_checked(status_text) else " "
                # Ordered list with GitHub-style checkbox
                lines.append(f"{item.position}. [{checked}] **{item.description or ''}**")
                # Tool and status line
                tool = item.tool or ""
                lines.append(f"   - **Tool:** `{tool}`")
                lines.append(f"   - **Status:** `{status_text or 'unknown'}`")
                # Parameters pretty-printed as JSON
                try:
                    params_json = json.dumps(item.parameters or {}, ensure_ascii=False, indent=2, sort_keys=True)
                except Exception:
                    # Fallback in case parameters aren't JSON-serializable
                    params_json = str(item.parameters)
                lines.append("   - **Parameters:**")
                lines.append("     ```json")
                # Indent each line of the JSON block so it nests nicely under the list item
                for ln in (params_json.splitlines() or ["{}"]):
                    lines.append(f"     {ln}")
                lines.append("     ```\n")

        # Open questions
        lines.append("## Open questions")
        if not self.open_questions:
            lines.append("_None._")
        else:
            for q in self.open_questions:
                lines.append(f"- {q}")

        # Final newline
        lines.append("")
        return "\n".join(lines)


class TodoListManager:
    def __init__(self, base_dir: str = "./checklists"):
        self.base_dir = base_dir


    async def extract_clarification_questions(self, mission: str, tools_desc: str) -> List[Dict[str, Any]]:
        """
        Extracts clarification questions from the mission and tools_desc.

        Args:
            mission: The mission to create the todolist for.
            tools_desc: The description of the tools available.

        Returns:
            A list of clarification questions.
        """
        user_prompt, system_prompt = self.create_clarification_questions_prompts(mission, tools_desc)
        response = await litellm.acompletion(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0  # deterministischer
        )
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)            
        except json.JSONDecodeError as e:
            # Optional: Fallback/Retry oder klare Fehlermeldung
            raise ValueError(f"Invalid JSON from model: {e}\nRaw: {raw[:500]}")
        return data



    def create_clarification_questions_prompts(self, mission: str, tools_desc: str) -> Tuple[str, str]:
        """
        Creates a prompt for clarification questions (Pre-Clarification).
        Returns (user_prompt, system_prompt).
        """
        system_prompt = f"""
    You are a Clarification-Mining Agent.

    ## Objective
    Find **all** missing required inputs needed to produce an **executable** plan for the mission using the available tools.

    ## Context
    - Mission (user intent and constraints):
    {mission}

    - Available tools (names, descriptions, **parameter schemas including required/optional/default/enums/types**):
    {tools_desc}

    ## Output
    - Return **only** a valid JSON array (no code fences, no commentary).
    - Each element must be:
    - "key": stable, machine-readable snake_case identifier. Prefer **"<tool>.<parameter>"** (e.g., "file_writer.filename"); if tool-agnostic use a clear domain key (e.g., "project_name").
    - "question": **one** short, closed, unambiguous question (one datum per question).

    ## Algorithm (mandatory)
    1) **Parse the mission** to understand the intended outcome and likely steps.
    2) **Enumerate candidate tool invocations** required to achieve the mission (internally; do not output them).
    3) For **each candidate tool**, inspect its **parameter schema**:
    - For every **required** parameter (or optional-without-safe-default) check if its value is **explicitly present** in the mission (exact literal or clearly specified constraint).
    - If not explicitly present, **create a question** for that parameter.
    4) **Respect schema constraints**:
    - Types (string/number/boolean/path/url/email), formats (e.g., kebab-case, ISO-8601), units, min/max.
    - If an enum is specified, ask as a **closed choice** (“Which of: A, B, or C?”).
    - **Do not infer** values unless a **default** is explicitly provided in the schema.
    5) **Merge & deduplicate** questions across tools.
    6) **Confidence gate**:
    - If you are **not 100% certain** every required value is specified, you **must** ask a question for it.
    - If truly nothing is missing, return **[]**.

    ## Strict Rules
    - **Only required info**: Ask only for parameters that are required (or effectively required because no safe default exists).
    - **No tasks, no explanations**: Output questions only.
    - **Closed & precise**:
    - Ask for a single value per question; include necessary format/units/constraints in the question.
    - Avoid ambiguity, multi-part questions, or small talk.
    - **Minimal & deduplicated**: No duplicates; no “nice-to-have” questions.

    ## Heuristic coverage (when relevant tools are present)
    - **File/Path tools**: confirm filename **with extension** and target **directory/path**; avoid ambiguous relative paths.
    - **Code/Project scaffolding**: project name (kebab-case), language/runtime version, package manager.
    - **Git/Repo**: repository name, visibility (public/private), remote provider, default branch, and **auth method/token** if required by schema.
    - **Network/Endpoints**: base URL/host, port, protocol (HTTP/HTTPS).
    - **Auth/Secrets**: explicit key names or secret identifiers if a tool schema requires them.

    ## Examples (illustrative only; do not force)
    [
    {{"key":"file_writer.filename","question":"What should the output file be called (include extension, e.g., report.txt)?"}},
    {{"key":"file_writer.directory","question":"In which directory should the file be created (absolute or project-relative path)?"}},
    {{"key":"git.create_repo.visibility","question":"Should the repository be public or private (choose one: public/private)?"}}
    ]
    """.strip()

        user_prompt = (
            'Provide the missing required information as a JSON array in the form '
            '[{"key":"<tool.parameter|domain_key>", "question":"<closed, precise question>"}]. '
            'If nothing is missing, return [].'
        )

        return user_prompt, system_prompt



    async def create_todolist(self, mission: str, tools_desc: str, answers: Any) -> TodoList:
        """
        Creates a new todolist based on the mission and tools_desc.

        Args:
            mission: The mission to create the todolist for.
            tools_desc: The description of the tools available.

        Returns:
            A new todolist based on the mission and tools_desc.

        Raises:
            ValueError: Invalid JSON from model.

        """
        user_prompt, system_prompt = self.create_final_todolist_prompts(mission, tools_desc, answers)

        response = await litellm.acompletion(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0  # deterministischer
        )

        # Sicheres Parsing
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            # Optional: Fallback/Retry oder klare Fehlermeldung
            raise ValueError(f"Invalid JSON from model: {e}\nRaw: {raw[:500]}")

        todolist = TodoList.from_json(data)
        self.__write_todolist(todolist)
        return todolist

    # def __validate_plan_schema(plan: dict, tool_names: set):
    #     if not isinstance(plan, dict):
    #         raise ValueError("Plan must be a JSON object.")
    #     if "items" not in plan or not isinstance(plan["items"], list):
    #         raise ValueError("Plan.items missing or not a list.")

    #     for step in plan["items"]:
    #         for key in ["id", "description", "tool", "parameters", "depends_on", "status"]:
    #             if key not in step:
    #                 raise ValueError(f"Missing field '{key}' in step.")
    #         if step["tool"] != "none" and step["tool"] not in tool_names:
    #             raise ValueError(f"Unknown tool '{step['tool']}'")
    #         if step["status"] not in {"PENDING", "BLOCKED", "DONE"}:
    #             raise ValueError(f"Invalid status '{step['status']}'")
    #         if not isinstance(step["depends_on"], list):
    #             raise ValueError("depends_on must be a list.")



    async def load_todolist(self, todolist_id: str) -> TodoList:
        """
        Loads a todolist from a file.

        Args:
            todolist_id: The id of the todolist to load.

        Returns:
            A todolist from a file.

        Raises:
            FileNotFoundError: If the todolist file is not found.
        """

        todolist_path = self.get_todolist_path(todolist_id)
        # check if the file exists
        if not todolist_path.exists():
            raise FileNotFoundError(f"Todolist file not found: {todolist_path}")

        # read the file
        with open(todolist_path, "r") as f:
            return TodoList.from_json(f.read())
    

    async def update_todolist(self, todolist: TodoList) -> TodoList:
        """
        Updates a todolist.

        Args:
            todolist: The todolist to update.
        """
        self.__write_todolist(todolist)
        return todolist
        

    async def get_todolist(self, todolist_id: str) -> TodoList:
        """
        Gets a todolist.
        
        Args:
            todolist_id: The id of the todolist to get.
        """
        todolist_path = self.get_todolist_path(todolist_id)
        if not todolist_path.exists():
            raise FileNotFoundError(f"Todolist file not found: {todolist_path}")
        with open(todolist_path, "r") as f:
            return TodoList.from_json(f.read())
        

    async def delete_todolist(self, todolist_id: str) -> bool:
        """
        Deletes a todolist.
        
        Args:
            todolist_id: The id of the todolist to delete.
        """
        todolist_path = self.get_todolist_path(todolist_id)
        if not todolist_path.exists():
            raise FileNotFoundError(f"Todolist file not found: {todolist_path}")
        todolist_path.unlink()
        return True


    def get_todolist_path(self, todolist_id: str) -> Path:
        """
        Gets the path to the todolist file.

        Args:
            todolist_id: The id of the todolist to get the path for.
        """
        return Path(self.base_dir) / f"todolist_{todolist_id}.json"


    def create_final_todolist_prompts(self, mission: str, tools_desc: str, answers: Any) -> Tuple[str, str]:
        """
        Creates a strict prompt for the final TodoList (No-ASK mode).
        Returns (user_prompt, system_prompt).
        """

        structure_block = """
    {
    "items": [
        {
        "id": "t1",
        "description": "Short, precise task description (1–2 sentences)",
        "tool": "tool_name_or_none",
        "parameters": {},
        "depends_on": [],
        "status": "PENDING"
        }
    ],
    "open_questions": [],
    "notes": ""
    }
        """.strip()

        system_prompt = f"""
    You are a planning agent. Your sole task is to convert the mission into a
    strict, executable TODO list. At this point, all required clarifications
    have already been collected — there must be **no questions left**.

    Context:

    - Mission:
    {mission}

    - Clarification Answers (already provided, use them directly):
    {answers}

    - Available tools (names, descriptions, parameter schemas):
    {tools_desc}

    ---

    ## Instructions

    1) OUTPUT FORMAT
    - Return a valid JSON object ONLY — no commentary, no code fences.
    - Match exactly the structure under "Expected JSON structure".

    2) PLAN REQUIREMENTS
    - Produce a minimal, complete, step-by-step plan to fulfill the mission.
    - Each step MUST be atomic (Single Responsibility).
    - Prefer fewer, well-scoped steps over many fuzzy steps.

    3) STEP FIELDS (MUST-HAVES)
    - id: short unique id like "t1", "t2", ...
    - description: 1–2 sentences, outcome-oriented.
    - tool: exact tool name from the provided list, or "none" if no tool is needed.
    - parameters: object with ONLY the required keys for the chosen tool (match the parameters_schema).
    - depends_on: array of step ids that must be completed first (empty if none).
    - status: always "PENDING" initially.

    4) PARAMETERS
    - Use the given Clarification Answers to fill in all required parameter values.
    - **Do not use "ASK_USER"**. Every parameter must be concrete.
    - Do not invent values — use only provided answers or explicit mission context.

    5) DEPENDENCIES
    - Add dependencies to enforce correct execution order.
    - No circular dependencies. All references must exist.

    6) QUALITY CHECKS BEFORE RETURNING
    - JSON is syntactically valid.
    - All tools exist (or "none").
    - parameters strictly conform to the tool’s parameters_schema (no extra keys).
    - All depends_on ids exist; no circular graphs.
    - **open_questions must always be empty**.

    ---

    ## Expected JSON structure
    {structure_block}
        """.strip()

        user_prompt = "Generate the final structured TODO list for the given mission (no questions, no ASK_USER placeholders)."

        return user_prompt, system_prompt


    def __write_todolist(self, todolist: TodoList) -> None:
        """
        Writes a todolist to a file.

        Args:
            todolist: The todolist to write to a file.
        """
        todolist_path = self.get_todolist_path(todolist.todolist_id)
        todolist_path.parent.mkdir(parents=True, exist_ok=True)
        todolist_path.write_text(todolist.to_json(), encoding="utf-8")

# Test function for complex mission requiring at least three tools and three steps
def test_todolist_creation():
    # Example tools description (for LLM context)
    tools_desc = (
        "- file_writer: Write content to a file. parameters_schema: {\"filename\": \"string\", \"content\": \"string\"}\n"
        "- web_search: Search the web for information. parameters_schema: {\"query\": \"string\"}\n"
        "- email_sender: Send an email. parameters_schema: {\"recipient\": \"string\", \"subject\": \"string\", \"body\": \"string\"}"
    )
    # Complex mission requiring all three tools
    mission = (
        "Research the latest advancements in AI, summarize the findings in a report.txt file, "
        "and email the report to the project manager at manager@example.com."
    )
    mission_context = {
        "user_request": "Please help me get an overview of the newest AI developments and send a summary to my manager.",
        "tools_desc": tools_desc,
        "context": "You have access to file_writer, web_search, and email_sender tools."
    }
    manager = TodoListManager()
    # Assuming create_todolist is async, but for test, we call it synchronously for illustration
    # In real test, use asyncio.run or pytest-asyncio
    import asyncio
    todolist = asyncio.run(manager.create_todolist(mission=mission, mission_context=mission_context))

    print("Todolist created:")
    print(todolist.to_json())
    pass





if __name__ == "__main__":
    test_todolist_creation()






