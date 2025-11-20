import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest  # type: ignore


from capstone.agent_v2.planning.todolist import (
    TaskStatus,
    parse_task_status,
    TodoItem,
    TodoList,
    TodoListManager,
)
from capstone.agent_v2.services.llm_service import LLMService


# -------------------------------
# Helpers
# -------------------------------
class FakeLLMResponse:
    def __init__(self, content: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService for tests."""
    service = MagicMock(spec=LLMService)
    service.complete = AsyncMock()
    return service


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
            acceptance_criteria="Step is complete",
            dependencies=[],
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
def test_get_todolist_path(tmp_path: Path, mock_llm_service):
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    p = m.get_todolist_path("abc")
    assert p == tmp_path / "todolist_abc.json"


# -------------------------------
# TodoListManager.create_final_todolist_prompts
# -------------------------------
def test_create_todolist_prompts_contains_expected_content(mock_llm_service):
    m = TodoListManager(base_dir="irrelevant", llm_service=mock_llm_service)
    mission = "Build a thing"
    tools_desc = "- tool_x: does x"
    user_prompt, system_prompt = m.create_final_todolist_prompts(mission, tools_desc, {})

    assert isinstance(user_prompt, str) and user_prompt
    assert isinstance(system_prompt, str) and mission in system_prompt
    assert "tool_x" in system_prompt
    assert '"items": [' in system_prompt


# -------------------------------
# TodoListManager.create_todolist (async)
# -------------------------------
def test_create_todolist_writes_file_and_returns_object(tmp_path: Path, mock_llm_service):
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)

    sample = make_sample_todolist_dict("create-id-1")
    fake_json = json.dumps(sample)

    # Mock LLMService response
    mock_llm_service.complete.return_value = {
        "success": True,
        "content": fake_json,
        "usage": {"total_tokens": 100}
    }

    todolist = asyncio.run(m.create_todolist(mission="x", tools_desc="z"))
    assert isinstance(todolist, TodoList)
    assert todolist.todolist_id == "create-id-1"

    # Verify LLMService was called
    mock_llm_service.complete.assert_called_once()
    call_args = mock_llm_service.complete.call_args
    assert call_args.kwargs["model"] == "fast"  # Should use fast model for todolist

    # File should be written
    path = m.get_todolist_path("create-id-1")
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["todolist_id"] == "create-id-1"


# -------------------------------
# TodoListManager.update/load/get/delete (async)
# -------------------------------
def test_update_load_get_delete_flow(tmp_path: Path, mock_llm_service):
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    tid = "flow-123"

    items = [
        TodoItem(position=1, description="d", acceptance_criteria="Done", dependencies=[], status=TaskStatus.PENDING)
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


def test_load_missing_raises(tmp_path: Path, mock_llm_service):
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    with pytest.raises(FileNotFoundError):
        asyncio.run(m.load_todolist("missing"))


def test_delete_missing_raises(tmp_path: Path, mock_llm_service):
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    with pytest.raises(FileNotFoundError):
        asyncio.run(m.delete_todolist("missing"))


# -------------------------------
# TodoItem.replan_count field
# -------------------------------
def test_todoitem_replan_count_default():
    """Test that replan_count defaults to 0."""
    item = TodoItem(
        position=1,
        description="test",
        acceptance_criteria="done"
    )
    assert item.replan_count == 0


def test_todoitem_replan_count_serialization():
    """Test that replan_count is serialized and deserialized correctly."""
    item = TodoItem(
        position=1,
        description="test",
        acceptance_criteria="done",
        replan_count=2
    )
    
    # Serialize
    item_dict = item.to_dict()
    assert item_dict["replan_count"] == 2
    
    # Deserialize via TodoList
    todolist = TodoList.from_json({
        "items": [item_dict],
        "open_questions": [],
        "notes": ""
    })
    assert todolist.items[0].replan_count == 2


def test_todolist_serialization_with_replan_count(tmp_path: Path):
    """Test that TodoList serialization includes replan_count."""
    items = [
        TodoItem(
            position=1,
            description="step",
            acceptance_criteria="done",
            replan_count=1
        )
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    
    # Serialize to JSON
    json_str = tl.to_json()
    data = json.loads(json_str)
    
    assert data["items"][0]["replan_count"] == 1
    
    # Deserialize and verify
    tl2 = TodoList.from_json(json_str)
    assert tl2.items[0].replan_count == 1


# -------------------------------
# TodoList helper methods
# -------------------------------
def test_get_step_by_position():
    """Test getting step by position."""
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done"),
        TodoItem(position=2, description="second", acceptance_criteria="done"),
    ]
    tl = TodoList(items=items, open_questions=[], notes="")
    
    step = tl.get_step_by_position(2)
    assert step is not None
    assert step.description == "second"
    
    # Non-existent position
    step = tl.get_step_by_position(99)
    assert step is None


def test_insert_step():
    """Test inserting a step and renumbering."""
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done"),
        TodoItem(position=2, description="second", acceptance_criteria="done"),
    ]
    tl = TodoList(items=items, open_questions=[], notes="")
    
    new_step = TodoItem(position=2, description="inserted", acceptance_criteria="done")
    tl.insert_step(new_step, at_position=2)
    
    # Should have 3 items
    assert len(tl.items) == 3
    
    # Items should be renumbered
    positions = [item.position for item in tl.items]
    assert sorted(positions) == [1, 2, 3]
    
    # Inserted step should be at position 2
    step2 = tl.get_step_by_position(2)
    assert step2.description == "inserted"
    
    # Original second step should be at position 3
    step3 = tl.get_step_by_position(3)
    assert step3.description == "second"


# -------------------------------
# TodoListManager._validate_dependencies
# -------------------------------
def test_validate_dependencies_valid(tmp_path: Path, mock_llm_service):
    """Test dependency validation with valid dependencies."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done", dependencies=[]),
        TodoItem(position=2, description="second", acceptance_criteria="done", dependencies=[1]),
        TodoItem(position=3, description="third", acceptance_criteria="done", dependencies=[1, 2]),
    ]
    tl = TodoList(items=items, open_questions=[], notes="")
    
    assert m._validate_dependencies(tl) is True


def test_validate_dependencies_invalid_reference(tmp_path: Path, mock_llm_service):
    """Test dependency validation detects invalid position references."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done", dependencies=[]),
        TodoItem(position=2, description="second", acceptance_criteria="done", dependencies=[99]),
    ]
    tl = TodoList(items=items, open_questions=[], notes="")
    
    assert m._validate_dependencies(tl) is False


def test_validate_dependencies_circular(tmp_path: Path, mock_llm_service):
    """Test dependency validation detects circular dependencies."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done", dependencies=[2]),
        TodoItem(position=2, description="second", acceptance_criteria="done", dependencies=[1]),
    ]
    tl = TodoList(items=items, open_questions=[], notes="")
    
    assert m._validate_dependencies(tl) is False


# -------------------------------
# TodoListManager.modify_step
# -------------------------------
def test_modify_step_success(tmp_path: Path, mock_llm_service):
    """Test successful step modification."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="original", acceptance_criteria="done", dependencies=[])
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    success, error = asyncio.run(m.modify_step(
        "test",
        1,
        {"description": "modified", "acceptance_criteria": "new criteria"}
    ))
    
    assert success is True
    assert error is None
    
    # Verify changes persisted
    updated_tl = asyncio.run(m.load_todolist("test"))
    step = updated_tl.get_step_by_position(1)
    assert step.description == "modified"
    assert step.acceptance_criteria == "new criteria"
    assert step.replan_count == 1
    assert step.status == TaskStatus.PENDING


def test_modify_step_replan_limit(tmp_path: Path, mock_llm_service):
    """Test that modify_step enforces replan limit."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="test", acceptance_criteria="done", replan_count=2)
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    success, error = asyncio.run(m.modify_step("test", 1, {"description": "fail"}))
    
    assert success is False
    assert "Max replan attempts" in error


def test_modify_step_nonexistent(tmp_path: Path, mock_llm_service):
    """Test modify_step with non-existent position."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [TodoItem(position=1, description="test", acceptance_criteria="done")]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    success, error = asyncio.run(m.modify_step("test", 99, {"description": "fail"}))
    
    assert success is False
    assert "not found" in error


def test_modify_step_invalid_dependencies(tmp_path: Path, mock_llm_service):
    """Test that modify_step rejects invalid dependency changes."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="first", acceptance_criteria="done", dependencies=[]),
        TodoItem(position=2, description="second", acceptance_criteria="done", dependencies=[1])
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    # Try to create circular dependency
    success, error = asyncio.run(m.modify_step("test", 1, {"dependencies": [2]}))
    
    assert success is False
    assert "invalid dependencies" in error.lower()


# -------------------------------
# TodoListManager.decompose_step
# -------------------------------
def test_decompose_step_success(tmp_path: Path, mock_llm_service):
    """Test successful step decomposition."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="original", acceptance_criteria="done", dependencies=[]),
        TodoItem(position=2, description="dependent", acceptance_criteria="done", dependencies=[1])
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    subtasks = [
        {"description": "subtask 1", "acceptance_criteria": "sub done 1"},
        {"description": "subtask 2", "acceptance_criteria": "sub done 2"},
    ]
    
    success, new_positions = asyncio.run(m.decompose_step("test", 1, subtasks))
    
    assert success is True
    assert len(new_positions) == 2
    
    # Verify changes
    updated_tl = asyncio.run(m.load_todolist("test"))
    
    # Original should be skipped
    original = updated_tl.get_step_by_position(1)
    assert original.status == TaskStatus.SKIPPED
    
    # Subtasks should exist
    sub1 = updated_tl.get_step_by_position(new_positions[0])
    sub2 = updated_tl.get_step_by_position(new_positions[1])
    assert sub1.description == "subtask 1"
    assert sub2.description == "subtask 2"
    
    # Second subtask should depend on first
    assert new_positions[0] in sub2.dependencies
    
    # Find the dependent item (it was originally at position 2, but got renumbered)
    # It should be the item with description "dependent"
    dependent = [item for item in updated_tl.items if item.description == "dependent"][0]
    assert new_positions[-1] in dependent.dependencies
    assert 1 not in dependent.dependencies


def test_decompose_step_replan_limit(tmp_path: Path, mock_llm_service):
    """Test that decompose_step enforces replan limit."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="test", acceptance_criteria="done", replan_count=2)
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    subtasks = [{"description": "sub", "acceptance_criteria": "done"}]
    success, positions = asyncio.run(m.decompose_step("test", 1, subtasks))
    
    assert success is False
    assert positions == []


def test_decompose_step_empty_subtasks(tmp_path: Path, mock_llm_service):
    """Test decompose_step with empty subtasks list."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [TodoItem(position=1, description="test", acceptance_criteria="done")]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    success, positions = asyncio.run(m.decompose_step("test", 1, []))
    
    assert success is False
    assert positions == []


# -------------------------------
# TodoListManager.replace_step
# -------------------------------
def test_replace_step_success(tmp_path: Path, mock_llm_service):
    """Test successful step replacement."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="original", acceptance_criteria="done", dependencies=[]),
        TodoItem(position=2, description="dependent", acceptance_criteria="done", dependencies=[1])
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    new_step_data = {
        "description": "replacement",
        "acceptance_criteria": "new done"
    }
    
    success, new_position = asyncio.run(m.replace_step("test", 1, new_step_data))
    
    assert success is True
    assert new_position == 1  # Same position
    
    # Verify changes
    updated_tl = asyncio.run(m.load_todolist("test"))
    
    # Should have original + replacement (3 items total, 1 is skipped)
    assert len([item for item in updated_tl.items if item.position == 1]) == 2
    
    # Find the non-skipped item at position 1
    active_step = [item for item in updated_tl.items if item.position == 1 and item.status != TaskStatus.SKIPPED][0]
    assert active_step.description == "replacement"
    assert active_step.replan_count == 1
    
    # Dependent should still reference position 1
    dependent = updated_tl.get_step_by_position(2)
    assert 1 in dependent.dependencies


def test_replace_step_replan_limit(tmp_path: Path, mock_llm_service):
    """Test that replace_step enforces replan limit."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [
        TodoItem(position=1, description="test", acceptance_criteria="done", replan_count=2)
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    new_step_data = {"description": "fail", "acceptance_criteria": "done"}
    success, position = asyncio.run(m.replace_step("test", 1, new_step_data))
    
    assert success is False
    assert position is None


def test_replace_step_nonexistent(tmp_path: Path, mock_llm_service):
    """Test replace_step with non-existent position."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    items = [TodoItem(position=1, description="test", acceptance_criteria="done")]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="test")
    asyncio.run(m.update_todolist(tl))
    
    new_step_data = {"description": "fail", "acceptance_criteria": "done"}
    success, position = asyncio.run(m.replace_step("test", 99, new_step_data))
    
    assert success is False
    assert position is None


# -------------------------------
# Integration test: Full modification workflow
# -------------------------------
def test_full_modification_workflow(tmp_path: Path, mock_llm_service):
    """Integration test: Create plan, modify, decompose, replace."""
    m = TodoListManager(base_dir=str(tmp_path), llm_service=mock_llm_service)
    
    # Create initial plan
    items = [
        TodoItem(position=1, description="step1", acceptance_criteria="done1", dependencies=[]),
        TodoItem(position=2, description="step2", acceptance_criteria="done2", dependencies=[1]),
        TodoItem(position=3, description="step3", acceptance_criteria="done3", dependencies=[2])
    ]
    tl = TodoList(items=items, open_questions=[], notes="", todolist_id="workflow")
    asyncio.run(m.update_todolist(tl))
    
    # 1. Modify step 1
    success, _ = asyncio.run(m.modify_step(
        "workflow", 1, {"description": "modified step1"}
    ))
    assert success is True
    
    # 2. Decompose step 2
    subtasks = [
        {"description": "step2a", "acceptance_criteria": "done2a"},
        {"description": "step2b", "acceptance_criteria": "done2b"}
    ]
    success, new_pos = asyncio.run(m.decompose_step("workflow", 2, subtasks))
    assert success is True
    assert len(new_pos) == 2
    
    # 3. Replace step 3
    success, _ = asyncio.run(m.replace_step(
        "workflow", 3, {"description": "replaced step3", "acceptance_criteria": "new done3"}
    ))
    assert success is True
    
    # Verify final state
    final_tl = asyncio.run(m.load_todolist("workflow"))
    
    # Step 1 modified
    step1 = [s for s in final_tl.items if s.position == 1 and s.status != TaskStatus.SKIPPED][0]
    assert step1.description == "modified step1"
    assert step1.replan_count == 1
    
    # Step 2 decomposed (should be skipped)
    step2_original = final_tl.get_step_by_position(2)
    assert step2_original.status == TaskStatus.SKIPPED
    
    # Step 3 replaced
    step3_active = [s for s in final_tl.items if s.position == 3 and s.status != TaskStatus.SKIPPED][0]
    assert step3_active.description == "replaced step3"
    
    # Validate dependencies are still correct
    assert m._validate_dependencies(final_tl) is True


