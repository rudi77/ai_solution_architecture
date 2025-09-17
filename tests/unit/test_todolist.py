import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest  # type: ignore


from capstone.agent_v2.planning.todolist import (
    TaskStatus,
    parse_task_status,
    TodoItem,
    TodoList,
    TodoListManager,
)


# -------------------------------
# Helpers
# -------------------------------
class FakeLLMResponse:
    def __init__(self, content: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


def make_sample_todolist_dict(todolist_id: str = "test-id-123") -> dict[str, Any]:
    return {
        "todolist_id": todolist_id,
        "items": [
            {
                "position": 1,
                "description": "Do something",
                "tool": "file_writer",
                "parameters": {"filename": "a.txt", "content": "hello"},
                "status": "PENDING",
            },
            {
                "position": 2,
                "description": "Search web",
                "tool": "web_search",
                "parameters": {"query": "ai news"},
                "status": "IN_PROGRESS",
            },
        ],
        "open_questions": ["oq1", "oq2"],
        "notes": "some notes",
    }


# -------------------------------
# parse_task_status
# -------------------------------
def test_parse_task_status_mappings():
    assert parse_task_status("open") == TaskStatus.PENDING
    assert parse_task_status("todo") == TaskStatus.PENDING
    assert parse_task_status("inprogress") == TaskStatus.IN_PROGRESS
    assert parse_task_status("done") == TaskStatus.COMPLETED
    assert parse_task_status("complete") == TaskStatus.COMPLETED
    assert parse_task_status("fail") == TaskStatus.FAILED
    assert parse_task_status("skipped") == TaskStatus.SKIPPED
    assert parse_task_status("unknown") == TaskStatus.PENDING
    assert parse_task_status(None) == TaskStatus.PENDING
    assert parse_task_status("IN_PROGRESS") == TaskStatus.IN_PROGRESS


# -------------------------------
# TodoList.from_json / to_dict / to_json
# -------------------------------
def test_todolist_from_json_with_dict_and_string():
    data = make_sample_todolist_dict()
    # From dict
    tl1 = TodoList.from_json(data)
    assert tl1.todolist_id == data["todolist_id"]
    assert len(tl1.items) == 2
    assert tl1.items[0].status == TaskStatus.PENDING
    assert tl1.items[1].status == TaskStatus.IN_PROGRESS
    assert tl1.open_questions == ["oq1", "oq2"]
    assert tl1.notes == "some notes"

    # From string
    tl2 = TodoList.from_json(json.dumps(data))
    assert tl2.todolist_id == data["todolist_id"]
    assert len(tl2.items) == 2


def test_todolist_to_dict_and_to_json_roundtrip():
    items = [
        TodoItem(
            position=1,
            description="step",
            tool="tool",
            parameters={"a": 1},
            status=TaskStatus.COMPLETED,
        )
    ]
    tl = TodoList(items=items, open_questions=["q"], notes="n", todolist_id="rid")
    as_dict = tl.to_dict()
    assert as_dict["todolist_id"] == "rid"
    assert as_dict["items"][0]["status"] == "COMPLETED"

    json_text = tl.to_json()
    tl2 = TodoList.from_json(json_text)
    assert tl2.todolist_id == tl.todolist_id
    assert len(tl2.items) == 1
    assert tl2.items[0].status == TaskStatus.COMPLETED


def test_todolist_from_json_handles_bad_input():
    # Malformed JSON returns fallbacks
    tl = TodoList.from_json("{ this is not json")
    assert isinstance(tl.todolist_id, str) and tl.todolist_id
    assert tl.items == []
    assert tl.open_questions == []
    assert isinstance(tl.notes, str)


# -------------------------------
# TodoListManager.get_todolist_path
# -------------------------------
def test_get_todolist_path(tmp_path: Path):
    m = TodoListManager(base_dir=str(tmp_path))
    p = m.get_todolist_path("abc")
    assert p == tmp_path / "todolist_abc.json"


# -------------------------------
# TodoListManager.create_todolist_prompts
# -------------------------------
def test_create_todolist_prompts_contains_expected_content():
    m = TodoListManager(base_dir="irrelevant")
    mission = "Build a thing"
    tools_desc = "- tool_x: does x"
    user_prompt, system_prompt = m.create_todolist_prompts(mission, tools_desc)

    assert isinstance(user_prompt, str) and user_prompt
    assert isinstance(system_prompt, str) and mission in system_prompt
    assert "tool_x" in system_prompt
    assert '"items": [' in system_prompt


# -------------------------------
# TodoListManager.create_todolist (async)
# -------------------------------
def test_create_todolist_writes_file_and_returns_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = TodoListManager(base_dir=str(tmp_path))

    sample = make_sample_todolist_dict("create-id-1")
    fake_json = json.dumps(sample)

    async def fake_acompletion(*args, **kwargs):
        return FakeLLMResponse(fake_json)

    import capstone.agent_v2.planning.todolist as tlmod
    monkeypatch.setattr(tlmod.litellm, "acompletion", fake_acompletion)

    todolist = asyncio.run(m.create_todolist(mission="x", tools_desc="z"))
    assert isinstance(todolist, TodoList)
    assert todolist.todolist_id == "create-id-1"

    # File should be written
    path = m.get_todolist_path("create-id-1")
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["todolist_id"] == "create-id-1"


# -------------------------------
# TodoListManager.update/load/get/delete (async)
# -------------------------------
def test_update_load_get_delete_flow(tmp_path: Path):
    m = TodoListManager(base_dir=str(tmp_path))
    tid = "flow-123"

    items = [
        TodoItem(position=1, description="d", tool="t", parameters={}, status=TaskStatus.PENDING)
    ]
    tlist = TodoList(items=items, open_questions=[], notes="n", todolist_id=tid)

    # update writes file
    res = asyncio.run(m.update_todolist(tlist))
    assert res.todolist_id == tid
    path = m.get_todolist_path(tid)
    assert path.exists()

    # load returns same logical content
    loaded = asyncio.run(m.load_todolist(tid))
    assert loaded.todolist_id == tid
    assert len(loaded.items) == 1
    assert loaded.items[0].description == "d"

    # get mirrors load
    got = asyncio.run(m.get_todolist(tid))
    assert got.todolist_id == tid

    # delete removes file
    ok = asyncio.run(m.delete_todolist(tid))
    assert ok is True
    assert not path.exists()


def test_load_missing_raises(tmp_path: Path):
    m = TodoListManager(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        asyncio.run(m.load_todolist("missing"))


def test_delete_missing_raises(tmp_path: Path):
    m = TodoListManager(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        asyncio.run(m.delete_todolist("missing"))


