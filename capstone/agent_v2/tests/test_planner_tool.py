# ============================================
# TESTS FOR PLANNER TOOL
# ============================================
"""Unit tests for PlannerTool - dynamic plan management."""
import pytest
from capstone.agent_v2.tools.planner_tool import PlannerTool


class TestPlannerToolCreatePlan:
    """Tests for create_plan action."""
    
    @pytest.mark.asyncio
    async def test_create_plan_success(self):
        """Creating a plan with valid tasks should succeed."""
        tool = PlannerTool()
        result = await tool.execute(action="create_plan", tasks=["Task 1", "Task 2", "Task 3"])
        
        assert result["success"] is True
        assert "3 tasks" in result["message"]
        assert "[ ] Task 1" in result["plan"]
        assert "[ ] Task 2" in result["plan"]
        assert "[ ] Task 3" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_create_plan_empty_list_fails(self):
        """Creating a plan with empty list should fail."""
        tool = PlannerTool()
        result = await tool.execute(action="create_plan", tasks=[])
        
        assert result["success"] is False
        assert "non-empty" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_plan_none_fails(self):
        """Creating a plan with None should fail."""
        tool = PlannerTool()
        result = await tool.execute(action="create_plan", tasks=None)
        
        assert result["success"] is False
        assert "non-empty" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_plan_no_tasks_param_fails(self):
        """Creating a plan without tasks param should fail."""
        tool = PlannerTool()
        result = await tool.execute(action="create_plan")
        
        assert result["success"] is False
        assert "non-empty" in result["error"]


class TestPlannerToolMarkDone:
    """Tests for mark_done action."""
    
    @pytest.mark.asyncio
    async def test_mark_done_success(self):
        """Marking a step done should update its status."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Task 1", "Task 2"])
        
        result = await tool.execute(action="mark_done", step_index=0)
        
        assert result["success"] is True
        assert "[x] Task 1" in result["plan"]
        assert "[ ] Task 2" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_mark_done_out_of_bounds_fails(self):
        """Marking a step with invalid index should fail."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Task 1"])
        
        result = await tool.execute(action="mark_done", step_index=5)
        
        assert result["success"] is False
        assert "out of bounds" in result["error"]
    
    @pytest.mark.asyncio
    async def test_mark_done_negative_index_fails(self):
        """Marking with negative index should fail."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Task 1"])
        
        result = await tool.execute(action="mark_done", step_index=-1)
        
        assert result["success"] is False
        assert "out of bounds" in result["error"]
    
    @pytest.mark.asyncio
    async def test_mark_done_no_plan_fails(self):
        """Marking done with no plan should fail."""
        tool = PlannerTool()
        result = await tool.execute(action="mark_done", step_index=0)
        
        assert result["success"] is False
        assert "No plan active" in result["error"]
    
    @pytest.mark.asyncio
    async def test_mark_done_missing_index_fails(self):
        """Marking done without step_index should fail."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Task 1"])
        
        result = await tool.execute(action="mark_done")
        
        assert result["success"] is False
        assert "step_index is required" in result["error"]


class TestPlannerToolReadPlan:
    """Tests for read_plan action."""
    
    @pytest.mark.asyncio
    async def test_read_plan_with_tasks(self):
        """Reading plan should return formatted Markdown."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Step A", "Step B"])
        
        result = await tool.execute(action="read_plan")
        
        assert result["success"] is True
        assert "0. [ ] Step A" in result["plan"]
        assert "1. [ ] Step B" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_read_plan_empty(self):
        """Reading empty plan should return 'No plan active'."""
        tool = PlannerTool()
        result = await tool.execute(action="read_plan")
        
        assert result["success"] is True
        assert result["plan"] == "No plan active"
    
    @pytest.mark.asyncio
    async def test_read_plan_mixed_status(self):
        """Reading plan with mixed done/not-done should show correctly."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Done", "Pending", "Also Done"])
        await tool.execute(action="mark_done", step_index=0)
        await tool.execute(action="mark_done", step_index=2)
        
        result = await tool.execute(action="read_plan")
        
        assert "[x] Done" in result["plan"]
        assert "[ ] Pending" in result["plan"]
        assert "[x] Also Done" in result["plan"]


class TestPlannerToolUpdatePlan:
    """Tests for update_plan action."""
    
    @pytest.mark.asyncio
    async def test_update_plan_add_steps(self):
        """Adding steps should append to plan."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Original"])
        
        result = await tool.execute(action="update_plan", add_steps=["New 1", "New 2"])
        
        assert result["success"] is True
        assert "Original" in result["plan"]
        assert "New 1" in result["plan"]
        assert "New 2" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_update_plan_remove_steps(self):
        """Removing steps by index should work."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["Keep", "Remove", "Also Keep"])
        
        result = await tool.execute(action="update_plan", remove_indices=[1])
        
        assert result["success"] is True
        assert "Keep" in result["plan"]
        assert "Remove" not in result["plan"]
        assert "Also Keep" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_update_plan_add_and_remove(self):
        """Adding and removing in same call should work."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["A", "B", "C"])
        
        result = await tool.execute(
            action="update_plan",
            remove_indices=[1],
            add_steps=["D"]
        )
        
        assert result["success"] is True
        assert "A" in result["plan"]
        assert "B" not in result["plan"]
        assert "C" in result["plan"]
        assert "D" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_update_plan_remove_invalid_index_ignored(self):
        """Removing invalid indices should be silently ignored."""
        tool = PlannerTool()
        await tool.execute(action="create_plan", tasks=["A", "B"])
        
        result = await tool.execute(action="update_plan", remove_indices=[99, -5])
        
        assert result["success"] is True
        assert "A" in result["plan"]
        assert "B" in result["plan"]
    
    @pytest.mark.asyncio
    async def test_update_plan_on_empty_plan(self):
        """Updating empty plan should work."""
        tool = PlannerTool()
        
        result = await tool.execute(action="update_plan", add_steps=["First"])
        
        assert result["success"] is True
        assert "First" in result["plan"]


class TestPlannerToolStateSerialization:
    """Tests for state get/set methods."""
    
    def test_get_state_returns_copy(self):
        """get_state should return a copy of internal state."""
        tool = PlannerTool()
        state = tool.get_state()
        state["tasks"] = [{"description": "Injected", "done": False}]
        
        # Internal state should be unchanged
        assert tool.get_state()["tasks"] == []
    
    def test_set_state_restores_tasks(self):
        """set_state should restore tasks correctly."""
        tool = PlannerTool()
        saved_state = {
            "tasks": [
                {"description": "Restored 1", "done": True},
                {"description": "Restored 2", "done": False}
            ]
        }
        
        tool.set_state(saved_state)
        
        state = tool.get_state()
        assert len(state["tasks"]) == 2
        assert state["tasks"][0]["done"] is True
    
    def test_set_state_with_none_resets(self):
        """set_state with None should reset to empty."""
        tool = PlannerTool()
        tool._state["tasks"] = [{"description": "Existing", "done": False}]
        
        tool.set_state(None)
        
        assert tool.get_state()["tasks"] == []
    
    def test_initial_state_constructor(self):
        """Constructor with initial_state should restore properly."""
        initial = {"tasks": [{"description": "From constructor", "done": False}]}
        tool = PlannerTool(initial_state=initial)
        
        state = tool.get_state()
        assert len(state["tasks"]) == 1
        assert state["tasks"][0]["description"] == "From constructor"
    
    @pytest.mark.asyncio
    async def test_roundtrip_serialization(self):
        """State should survive get/set roundtrip."""
        tool1 = PlannerTool()
        await tool1.execute(action="create_plan", tasks=["A", "B", "C"])
        await tool1.execute(action="mark_done", step_index=1)
        
        saved_state = tool1.get_state()
        
        tool2 = PlannerTool()
        tool2.set_state(saved_state)
        
        result = await tool2.execute(action="read_plan")
        assert "[ ] A" in result["plan"]
        assert "[x] B" in result["plan"]
        assert "[ ] C" in result["plan"]


class TestPlannerToolUnknownAction:
    """Tests for unknown action handling."""
    
    @pytest.mark.asyncio
    async def test_unknown_action_fails(self):
        """Unknown action should return error."""
        tool = PlannerTool()
        result = await tool.execute(action="invalid_action")
        
        assert result["success"] is False
        assert "Unknown action" in result["error"]
        assert "invalid_action" in result["error"]


class TestPlannerToolMetadata:
    """Tests for tool metadata properties."""
    
    def test_name_property(self):
        """Tool name should be 'planner'."""
        tool = PlannerTool()
        assert tool.name == "planner"
    
    def test_description_property(self):
        """Tool description should mention all actions."""
        tool = PlannerTool()
        desc = tool.description
        assert "create_plan" in desc
        assert "mark_done" in desc
        assert "read_plan" in desc
        assert "update_plan" in desc
    
    def test_parameters_schema_structure(self):
        """Parameter schema should define action enum."""
        tool = PlannerTool()
        schema = tool.parameters_schema
        
        assert schema["type"] == "object"
        assert "action" in schema["properties"]
        assert schema["properties"]["action"]["enum"] == [
            "create_plan", "mark_done", "read_plan", "update_plan"
        ]
        assert "action" in schema["required"]

