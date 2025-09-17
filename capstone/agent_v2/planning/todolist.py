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

class TodoListManager:
    def __init__(self, base_dir: str = "./checklists"):
        self.base_dir = base_dir


    async def create_todolist(self, mission: str, tools_desc: str) -> TodoList:
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
        user_prompt, system_prompt = self.create_todolist_prompts(mission, tools_desc)

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


    def create_todolist_prompts(self, mission: str, tools_desc: str) -> Tuple[str, str]:
        """
        Gibt (user_prompt, system_prompt) zurück, passend für den Planungs-Agenten.
        """

        # Einheitliches, minimales und konsistentes Schema
        structure_block = """
    {
    "items": [
        {
        "id": "t1",
        "description": "Kurze, präzise Aufgabenbeschreibung (1–2 Sätze)",
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
    structured execution plan (TODO list).

    Context you have:

    - Mission:
    {mission}

    - Available tools (names, descriptions, parameter schemas):
    {tools_desc}

    ---

    ## Instructions

    1) OUTPUT FORMAT
    - Return a valid JSON object ONLY — no extra commentary, no code fences.
    - Use exactly the structure shown under "Expected JSON structure".

    2) PLAN REQUIREMENTS
    - Produce a minimal, complete step-by-step plan to fulfill the mission.
    - Each step MUST be atomic (Single Responsibility).
    - Prefer fewer, well-scoped steps over many fuzzy steps.

    3) STEP FIELDS (MUST-HAVES)
    - id: short unique id like "t1", "t2", ...
    - description: 1–2 sentences, clear and outcome-oriented.
    - tool: exact tool name from the provided list, or "none" if no tool is needed.
    - parameters: object with ONLY the required keys for the chosen tool (match the parameters_schema).
    - depends_on: array of step ids that must be completed first (empty if none).
    - status: one of "PENDING", "BLOCKED", "DONE" (initially use "PENDING"; use "BLOCKED" only if the step cannot start without user input).

    4) PARAMETERS
    - If a parameter value is unknown and must be clarified: 
    - Put the placeholder string "ASK_USER" as the value in parameters,
    - AND add a corresponding human-readable question to "open_questions".

    5) DEPENDENCIES
    - Add dependencies to enforce correct execution order.
    - No circular dependencies. All references must exist.

    6) QUALITY CHECKS BEFORE RETURNING
    - JSON is syntactically valid.
    - All tools exist (or "none").
    - parameters strictly conform to the target tool's parameters_schema (no extra keys).
    - All depends_on ids exist; no circular graphs.
    - If any "ASK_USER" appears, ensure "open_questions" contains precise, actionable questions.

    ---

    ## Expected JSON structure
    {structure_block}
        """.strip()

        # Der UserPrompt an den Planungs-Agenten ist bewusst generisch
        user_prompt = "Generate the structured TODO list for the given mission."

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






