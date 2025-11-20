"""Integration tests for approval gate workflow (Story 2.2).

Tests the agent's approval gate functionality:
1. Approval request flow (approve, deny, trust scenarios)
2. Approval cache persistence across multiple tool calls
3. StateManager serialization/deserialization with approval fields
"""

import asyncio
import pytest
from pathlib import Path
import tempfile
import shutil
import os
from unittest.mock import AsyncMock, MagicMock

from capstone.agent_v2.agent import Agent, AgentEventType
from capstone.agent_v2.agent_factory import create_standard_agent
from capstone.agent_v2.planning.todolist import TaskStatus
from capstone.agent_v2.statemanager import StateManager
from capstone.agent_v2.tools.file_tool import FileWriteTool


@pytest.mark.integration
class TestApprovalWorkflow:
    """Test approval workflow integration."""
    
    @pytest.fixture
    def temp_work_dir(self):
        """Create temporary work directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def test_file_path(self, temp_work_dir):
        """Create a test file path."""
        return temp_work_dir / "test_file.txt"
    
    @pytest.mark.asyncio
    async def test_approval_workflow_approve_scenario(self, temp_work_dir, test_file_path):
        """
        Test AC #10: Approval workflow - approve scenario.
        
        Scenario:
        1. Simulate approval request by setting pending_question
        2. User responds "y" (approve)
        3. Verify approval processed and cached
        """
        session_id = "test_approval_approve_001"
        agent = create_standard_agent(
            name="Test Agent",
            description="Test agent for approval workflow",
            work_dir=str(temp_work_dir)
        )
        
        # Initialize state
        agent.state = {
            "approval_cache": {},
            "trust_mode": False,
            "approval_history": [],
            "answers": {}
        }
        
        # Simulate approval request (as agent would set it)
        from capstone.agent_v2.tools.file_tool import FileWriteTool
        tool = FileWriteTool()
        approval_key = "approval_step_1_file_write_0"
        
        # Set pending question (simulating agent's approval request)
        agent.state["pending_question"] = {
            "answer_key": approval_key,
            "question": agent._build_approval_prompt(tool, {"path": str(test_file_path), "content": "Hello World"}),
            "for_step": 1
        }
        
        # User approves
        user_response = "y"
        agent.state["answers"][approval_key] = user_response
        
        # Process approval response
        approved = agent._process_approval_response(user_response, tool, 1)
        
        # Verify approval was processed
        assert approved is True, "Approval should be granted"
        assert agent.state.get("approval_cache", {}).get("file_write") is True, \
            "Approval cache should contain file_write=True"
        
        # Verify approval history
        approval_history = agent.state.get("approval_history", [])
        assert len(approval_history) > 0, "Approval history should contain at least one record"
        last_record = approval_history[-1]
        assert last_record["tool"] == "file_write"
        assert last_record["decision"] == "approved"
    
    @pytest.mark.asyncio
    async def test_approval_workflow_deny_scenario(self, temp_work_dir, test_file_path):
        """
        Test AC #10: Approval workflow - deny scenario.
        
        Scenario:
        1. Simulate approval request
        2. User responds "n" (deny)
        3. Verify approval denied and step would be skipped
        """
        session_id = "test_approval_deny_001"
        agent = create_standard_agent(
            name="Test Agent",
            description="Test agent for approval workflow",
            work_dir=str(temp_work_dir)
        )
        
        # Initialize state
        agent.state = {
            "approval_cache": {},
            "trust_mode": False,
            "approval_history": [],
            "answers": {}
        }
        
        # Simulate approval request
        from capstone.agent_v2.tools.file_tool import FileWriteTool
        tool = FileWriteTool()
        approval_key = "approval_step_1_file_write_0"
        
        agent.state["pending_question"] = {
            "answer_key": approval_key,
            "question": agent._build_approval_prompt(tool, {"path": str(test_file_path), "content": "Hello World"}),
            "for_step": 1
        }
        
        # User denies
        user_response = "n"
        agent.state["answers"][approval_key] = user_response
        
        # Process approval response
        approved = agent._process_approval_response(user_response, tool, 1)
        
        # Verify approval was denied
        assert approved is False, "Approval should be denied"
        assert "file_write" not in agent.state.get("approval_cache", {}), \
            "Approval cache should NOT contain file_write when denied"
        
        # Verify approval history
        approval_history = agent.state.get("approval_history", [])
        assert len(approval_history) > 0, "Approval history should contain denial record"
        last_record = approval_history[-1]
        assert last_record["decision"] == "denied"
    
    @pytest.mark.asyncio
    async def test_approval_workflow_trust_scenario(self, temp_work_dir, test_file_path):
        """
        Test AC #10: Approval workflow - trust scenario.
        
        Scenario:
        1. Simulate approval request
        2. User responds "trust" (approve all)
        3. Verify trust mode enabled
        4. Verify subsequent checks bypass approval
        """
        session_id = "test_approval_trust_001"
        agent = create_standard_agent(
            name="Test Agent",
            description="Test agent for approval workflow",
            work_dir=str(temp_work_dir)
        )
        
        # Initialize state
        agent.state = {
            "approval_cache": {},
            "trust_mode": False,
            "approval_history": [],
            "answers": {}
        }
        
        # Simulate approval request
        from capstone.agent_v2.tools.file_tool import FileWriteTool
        tool = FileWriteTool()
        approval_key = "approval_step_1_file_write_0"
        
        agent.state["pending_question"] = {
            "answer_key": approval_key,
            "question": agent._build_approval_prompt(tool, {"path": str(test_file_path), "content": "Hello World"}),
            "for_step": 1
        }
        
        # User trusts
        user_response = "trust"
        agent.state["answers"][approval_key] = user_response
        
        # Process approval response
        approved = agent._process_approval_response(user_response, tool, 1)
        
        # Verify trust mode enabled
        assert approved is True, "Approval should be granted for trust"
        assert agent.state.get("trust_mode") is True, "Trust mode should be enabled"
        
        # Verify approval history
        approval_history = agent.state.get("approval_history", [])
        assert len(approval_history) > 0, "Approval history should contain trust record"
        last_record = approval_history[-1]
        assert last_record["decision"] == "trusted"
        
        # Verify subsequent tool calls bypass approval (trust mode check)
        assert agent._check_approval_granted(tool) is True, \
            "Approval should be granted when trust_mode is True"
    
    @pytest.mark.asyncio
    async def test_approval_cache_persistence(self, temp_work_dir, test_file_path):
        """
        Test AC #11: Approval cache persistence across multiple tool calls.
        
        Scenario:
        1. User approves FileWriteTool ("y")
        2. Approval cached
        3. Second check for same tool should use cache (no approval request)
        """
        session_id = "test_approval_cache_001"
        agent = create_standard_agent(
            name="Test Agent",
            description="Test agent for approval cache",
            work_dir=str(temp_work_dir)
        )
        
        # Initialize state
        agent.state = {
            "approval_cache": {},
            "trust_mode": False,
            "approval_history": [],
            "answers": {}
        }
        
        from capstone.agent_v2.tools.file_tool import FileWriteTool
        tool = FileWriteTool()
        
        # First approval
        approval_key_1 = "approval_step_1_file_write_0"
        user_response_1 = "y"
        agent.state["answers"][approval_key_1] = user_response_1
        
        approved_1 = agent._process_approval_response(user_response_1, tool, 1)
        assert approved_1 is True
        
        # Verify approval cached
        assert agent.state.get("approval_cache", {}).get("file_write") is True, \
            "Approval should be cached after first approval"
        
        # Second check - should use cache (no approval needed)
        assert agent._check_approval_granted(tool) is True, \
            "Second check should use cache and return True"
        
        # Verify cache persists
        assert agent.state.get("approval_cache", {}).get("file_write") is True, \
            "Approval cache should persist for subsequent calls"
    
    @pytest.mark.asyncio
    async def test_statemanager_serialization_with_approval_fields(self, temp_work_dir):
        """
        Test AC #13: StateManager serialization/deserialization with new approval fields.
        
        Scenario:
        1. Create state with approval fields (approval_cache, trust_mode, approval_history)
        2. Save state via StateManager
        3. Load state via StateManager
        4. Verify all approval fields are preserved
        """
        session_id = "test_state_serialization_001"
        state_manager = StateManager(state_dir=str(temp_work_dir / "states"))
        
        # Create state with approval fields
        test_state = {
            "todolist_id": "test_todolist_001",
            "answers": {},
            "approval_cache": {"file_write": True, "git": False},
            "trust_mode": True,
            "approval_history": [
                {
                    "timestamp": "2025-01-20T10:00:00",
                    "tool": "file_write",
                    "step": 1,
                    "risk": "medium",
                    "decision": "approved"
                },
                {
                    "timestamp": "2025-01-20T10:01:00",
                    "tool": "git",
                    "step": 2,
                    "risk": "high",
                    "decision": "trusted"
                }
            ]
        }
        
        # Save state
        save_result = await state_manager.save_state(session_id, test_state)
        assert save_result is True, "State should save successfully"
        
        # Load state
        loaded_state = await state_manager.load_state(session_id)
        assert loaded_state is not None, "State should load successfully"
        
        # Verify approval fields preserved
        assert "approval_cache" in loaded_state, "approval_cache should be preserved"
        assert loaded_state["approval_cache"] == test_state["approval_cache"], \
            "approval_cache should match saved value"
        
        assert "trust_mode" in loaded_state, "trust_mode should be preserved"
        assert loaded_state["trust_mode"] == test_state["trust_mode"], \
            "trust_mode should match saved value"
        
        assert "approval_history" in loaded_state, "approval_history should be preserved"
        assert len(loaded_state["approval_history"]) == len(test_state["approval_history"]), \
            "approval_history length should match"
        assert loaded_state["approval_history"][0]["decision"] == "approved", \
            "approval_history records should be preserved"
        assert loaded_state["approval_history"][1]["decision"] == "trusted", \
            "approval_history records should be preserved"
    
    @pytest.mark.asyncio
    async def test_statemanager_backward_compatibility(self, temp_work_dir):
        """
        Test AC #13: StateManager backward compatibility with old state files.
        
        Scenario:
        1. Create old state file without approval fields
        2. Load state via StateManager
        3. Agent should handle missing fields gracefully (via setdefault)
        """
        session_id = "test_state_backward_compat_001"
        state_manager = StateManager(state_dir=str(temp_work_dir / "states"))
        
        # Create old-style state (without approval fields)
        old_state = {
            "todolist_id": "test_todolist_001",
            "answers": {},
            # No approval_cache, trust_mode, or approval_history
        }
        
        # Save old state
        save_result = await state_manager.save_state(session_id, old_state)
        assert save_result is True, "Old state should save successfully"
        
        # Load state
        loaded_state = await state_manager.load_state(session_id)
        assert loaded_state is not None, "Old state should load successfully"
        
        # Verify old state loads correctly
        assert "todolist_id" in loaded_state
        assert loaded_state["todolist_id"] == "test_todolist_001"
        
        # Verify approval fields are NOT present (backward compatibility)
        # Agent will use setdefault() to initialize them
        assert "approval_cache" not in loaded_state or loaded_state.get("approval_cache") is None
        assert "trust_mode" not in loaded_state or loaded_state.get("trust_mode") is None
        assert "approval_history" not in loaded_state or loaded_state.get("approval_history") is None
        
        # Simulate agent initialization (setdefault pattern)
        loaded_state.setdefault("approval_cache", {})
        loaded_state.setdefault("trust_mode", False)
        loaded_state.setdefault("approval_history", [])
        
        # Verify defaults applied
        assert loaded_state["approval_cache"] == {}
        assert loaded_state["trust_mode"] is False
        assert loaded_state["approval_history"] == []

