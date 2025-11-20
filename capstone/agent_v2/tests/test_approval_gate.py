import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from capstone.agent_v2.agent import Agent, Action, ActionType
from capstone.agent_v2.tool import Tool, ApprovalRiskLevel

# Tests for Story 2.2 Approval Gate
class SensitiveTool(Tool):
    @property
    def name(self):
        return "sensitive_tool"
    @property
    def description(self):
        return "A sensitive tool"
    @property
    def requires_approval(self):
        return True
    @property
    def approval_risk_level(self):
        return ApprovalRiskLevel.HIGH
    async def execute(self, **kwargs):
        return {"success": True}

@pytest.fixture
def agent():
    agent = MagicMock(spec=Agent)
    # Use real methods for what we want to test
    agent._check_approval_granted = Agent._check_approval_granted.__get__(agent, Agent)
    agent._process_approval_response = Agent._process_approval_response.__get__(agent, Agent)
    agent._build_approval_prompt = Agent._build_approval_prompt.__get__(agent, Agent)
    
    # Initialize state
    agent.state = {
        "approval_cache": {}, 
        "trust_mode": False,
        "approval_history": []
    }
    return agent

def test_check_approval_granted(agent):
    tool = SensitiveTool()
    
    # Default: False
    assert agent._check_approval_granted(tool) is False
    
    # Trust Mode: True
    agent.state["trust_mode"] = True
    assert agent._check_approval_granted(tool) is True
    
    # Cache: True
    agent.state["trust_mode"] = False
    agent.state["approval_cache"]["sensitive_tool"] = True
    assert agent._check_approval_granted(tool) is True

def test_process_approval_response_yes(agent):
    tool = SensitiveTool()
    
    approved = agent._process_approval_response("y", tool, 1)
    assert approved is True
    assert agent.state["approval_cache"]["sensitive_tool"] is True
    assert len(agent.state["approval_history"]) == 1
    assert agent.state["approval_history"][0]["decision"] == "approved"

def test_process_approval_response_no(agent):
    tool = SensitiveTool()
    
    approved = agent._process_approval_response("n", tool, 1)
    assert approved is False
    assert "sensitive_tool" not in agent.state["approval_cache"]
    assert len(agent.state["approval_history"]) == 1
    assert agent.state["approval_history"][0]["decision"] == "denied"

def test_process_approval_response_trust(agent):
    tool = SensitiveTool()
    
    approved = agent._process_approval_response("trust", tool, 1)
    assert approved is True
    assert agent.state["trust_mode"] is True
    assert len(agent.state["approval_history"]) == 1
    assert agent.state["approval_history"][0]["decision"] == "trusted"

def test_build_approval_prompt(agent):
    tool = SensitiveTool()
    prompt = agent._build_approval_prompt(tool, {"param": "value"})
    
    assert "Approval Required [high]" in prompt
    assert "A sensitive tool" in prompt
    assert "Approve this operation? (y/n/trust)" in prompt
