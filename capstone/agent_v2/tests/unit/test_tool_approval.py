import pytest
from capstone.agent_v2.tool import Tool, ApprovalRiskLevel

class MockTool(Tool):
    @property
    def name(self): return "mock"
    @property
    def description(self): return "mock tool"
    async def execute(self, **kwargs): return {}

class HighRiskTool(MockTool):
    @property
    def requires_approval(self): return True
    @property
    def approval_risk_level(self): return ApprovalRiskLevel.HIGH

class MediumRiskTool(MockTool):
    @property
    def requires_approval(self): return True
    # Default risk is MEDIUM if requires_approval is True

def test_tool_defaults():
    t = MockTool()
    assert t.requires_approval is False
    assert t.approval_risk_level == ApprovalRiskLevel.LOW
    assert "Tool: mock" in t.get_approval_preview(param="val")

def test_high_risk_tool():
    t = HighRiskTool()
    assert t.requires_approval is True
    assert t.approval_risk_level == ApprovalRiskLevel.HIGH

def test_medium_risk_tool():
    t = MediumRiskTool()
    assert t.requires_approval is True
    # Check default logic for risk level
    assert t.approval_risk_level == ApprovalRiskLevel.MEDIUM

def test_approval_preview():
    t = MockTool()
    preview = t.get_approval_preview(foo="bar", baz=123)
    assert "foo" in preview
    assert "bar" in preview
    assert "baz" in preview

# Test specific tools
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.file_tool import FileWriteTool
from capstone.agent_v2.tools.git_tool import GitTool

def test_powershell_tool_approval():
    t = PowerShellTool()
    assert t.requires_approval is True
    assert t.approval_risk_level == ApprovalRiskLevel.HIGH

def test_file_write_tool_approval():
    t = FileWriteTool()
    assert t.requires_approval is True
    assert t.approval_risk_level == ApprovalRiskLevel.MEDIUM

def test_git_tool_approval():
    t = GitTool()
    assert t.requires_approval is True
    assert t.approval_risk_level == ApprovalRiskLevel.HIGH
    
    # Test preview override
    preview = t.get_approval_preview(operation="push", remote="upstream", branch="dev")
    assert "GIT PUSH OPERATION" in preview
    assert "upstream" in preview
    assert "dev" in preview
    
    # Test preview non-push
    preview_status = t.get_approval_preview(operation="status")
    assert "GIT PUSH" not in preview_status
    assert "status" in preview_status

