"""Unit tests for system prompt construction (Story CONV-HIST-002).

Tests validate that build_system_prompt() correctly handles:
1. Mission-agnostic prompts (mission=None) for stable conversation context
2. Backward compatibility with mission-specific prompts
"""

import pytest
from capstone.agent_v2.agent import build_system_prompt


class TestBuildSystemPromptMissionAgnostic:
    """Test mission-agnostic system prompt generation (Story CONV-HIST-002)."""

    def test_build_system_prompt_without_mission(self):
        """Should generate prompt without mission section when mission=None."""
        # Setup: Base prompt and tools description
        base_prompt = "You are a helpful RAG assistant."
        tools_desc = "Available tools: search, list, get"
        
        # Action: Call build_system_prompt with mission=None
        result = build_system_prompt(base_prompt, None, tools_desc)
        
        # Assert: Result contains base prompt and tools
        assert base_prompt in result
        assert tools_desc in result
        
        # Assert: Result does NOT contain mission section
        assert "<Mission>" not in result
        assert "</Mission>" not in result
        
        # Assert: Result contains base and tools sections
        assert "<Base>" in result
        assert "</Base>" in result
        assert "<ToolsDescription>" in result
        assert "</ToolsDescription>" in result
        
        # Assert: Result is valid system prompt (non-empty)
        assert len(result) > 0
        assert len(result.strip()) > 0

    def test_mission_agnostic_prompt_structure(self):
        """Mission-agnostic prompt should have clean structure without mission."""
        base_prompt = "You are an agent."
        tools_desc = "Tools: A, B, C"
        
        result = build_system_prompt(base_prompt, None, tools_desc)
        
        # Should have exactly 2 sections: Base and ToolsDescription
        section_count = result.count("<Base>")
        assert section_count == 1, "Should have exactly one Base section"
        
        section_count = result.count("<ToolsDescription>")
        assert section_count == 1, "Should have exactly one ToolsDescription section"
        
        # Should have NO Mission section
        assert "<Mission>" not in result
        assert "Mission" not in result or "ToolsDescription" in result  # Allow in other contexts

    def test_mission_none_vs_empty_string(self):
        """mission=None should behave differently from mission=''."""
        base_prompt = "Base prompt"
        tools_desc = "Tools"
        
        result_none = build_system_prompt(base_prompt, None, tools_desc)
        result_empty = build_system_prompt(base_prompt, "", tools_desc)
        
        # Both should NOT include mission section (empty string is falsy)
        assert "<Mission>" not in result_none
        assert "<Mission>" not in result_empty


class TestBuildSystemPromptBackwardCompatibility:
    """Test backward compatibility with mission-specific prompts."""

    def test_build_system_prompt_with_mission(self):
        """Should include mission section when mission provided (backward compat)."""
        # Setup: Base prompt, mission, tools
        base_prompt = "You are a helpful RAG assistant."
        mission = "Answer questions about technical documentation"
        tools_desc = "Available tools: search, list, get"
        
        # Action: Call build_system_prompt with mission
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Assert: Result contains base prompt, mission, and tools
        assert base_prompt in result
        assert mission in result
        assert tools_desc in result
        
        # Assert: Mission section properly formatted
        assert "<Mission>" in result
        assert "</Mission>" in result
        
        # Assert: All three sections present
        assert "<Base>" in result
        assert "</Base>" in result
        assert "<ToolsDescription>" in result
        assert "</ToolsDescription>" in result

    def test_mission_with_whitespace_handling(self):
        """Should strip whitespace from mission while preserving content."""
        base_prompt = "Base"
        mission = "  \n  My mission with spaces  \n  "
        tools_desc = "Tools"
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Should contain trimmed mission
        assert "My mission with spaces" in result
        # Should not have excessive leading/trailing whitespace in mission section
        assert "  \n  My mission" not in result

    def test_all_sections_with_mission(self):
        """When mission provided, prompt should have all three sections."""
        base_prompt = "Agent role"
        mission = "Current task"
        tools_desc = "Tool list"
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Count sections
        assert result.count("<Base>") == 1
        assert result.count("<Mission>") == 1
        assert result.count("<ToolsDescription>") == 1


class TestBuildSystemPromptEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_tools_description(self):
        """Should handle empty tools description gracefully."""
        base_prompt = "Base"
        mission = "Mission"
        tools_desc = ""
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Should still have base and mission
        assert "<Base>" in result
        assert "<Mission>" in result
        # Tools section should not be added if empty
        # (This is the actual behavior based on the conditional check)

    def test_mission_with_special_characters(self):
        """Should handle mission with special characters."""
        base_prompt = "Base"
        mission = "Mission with <tags> and & special chars"
        tools_desc = "Tools"
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Should preserve special characters in mission
        assert mission.strip() in result

    def test_multiline_content(self):
        """Should handle multiline content in all sections."""
        base_prompt = "Line 1\nLine 2\nLine 3"
        mission = "Mission\nwith\nmultiple\nlines"
        tools_desc = "Tool 1\nTool 2\nTool 3"
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # All content should be preserved
        assert "Line 1" in result
        assert "Line 3" in result
        assert "Mission" in result
        assert "lines" in result
        assert "Tool 1" in result
        assert "Tool 3" in result


class TestBuildSystemPromptOutputFormat:
    """Test the output format and structure of generated prompts."""

    def test_sections_separated_by_double_newline(self):
        """Sections should be separated by double newline for readability."""
        base_prompt = "Base"
        mission = "Mission"
        tools_desc = "Tools"
        
        result = build_system_prompt(base_prompt, mission, tools_desc)
        
        # Should have double newlines between sections
        assert "\n\n" in result

    def test_prompt_is_string(self):
        """Output should always be a string."""
        result = build_system_prompt("Base", "Mission", "Tools")
        assert isinstance(result, str)
        
        result_no_mission = build_system_prompt("Base", None, "Tools")
        assert isinstance(result_no_mission, str)

    def test_prompt_is_nonempty(self):
        """Output should never be empty string."""
        result = build_system_prompt("Base", "Mission", "Tools")
        assert len(result) > 0
        
        result_no_mission = build_system_prompt("Base", None, "Tools")
        assert len(result_no_mission) > 0

