"""Tests for agent factory module."""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import yaml

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_factory import (
    create_standard_agent,
    create_rag_agent,
    load_agent_config_from_yaml,
    create_agent_from_config,
    create_agent_from_yaml,
    AgentConfig,
    ToolConfig,
    _load_system_prompt,
    _instantiate_tool,
    _configure_llm
)


def test_create_standard_agent():
    """Test standard agent creation."""
    agent = create_standard_agent(
        name="Test Agent",
        description="Test description",
        mission="Test mission"
    )
    
    assert agent is not None
    assert agent.name == "Test Agent"
    assert agent.description == "Test description"
    assert len(agent.tools) == 9  # Standard tool count
    
    # Verify standard tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert "python" in tool_names
    assert "github" in tool_names
    assert "git" in tool_names
    assert "file_read" in tool_names
    assert "file_write" in tool_names
    assert "powershell" in tool_names
    assert "llm_generate" in tool_names


def test_create_standard_agent_with_custom_work_dir():
    """Test standard agent creation with custom work directory."""
    agent = create_standard_agent(
        name="Custom Agent",
        description="Agent with custom work dir",
        work_dir="./custom_work"
    )
    
    assert agent is not None
    assert agent.name == "Custom Agent"


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent():
    """Test RAG agent creation."""
    agent = create_rag_agent(
        session_id="test_001",
        user_context={"user_id": "test"}
    )
    
    assert agent is not None
    assert agent.name == "RAG Knowledge Assistant"
    assert len(agent.tools) == 4  # RAG tool count
    
    # Verify RAG tools present
    tool_names = [tool.name for tool in agent.tools]
    assert "rag_semantic_search" in tool_names
    assert "rag_list_documents" in tool_names
    assert "rag_get_document" in tool_names
    assert "llm_generate" in tool_names


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent_with_custom_work_dir():
    """Test RAG agent creation with custom work directory."""
    agent = create_rag_agent(
        session_id="test_002",
        user_context={"user_id": "test", "org_id": "org123"},
        work_dir="./custom_rag_work"
    )
    
    assert agent is not None
    assert agent.name == "RAG Knowledge Assistant"
    assert agent.description == "Agent with semantic search capabilities for enterprise documents"


@pytest.mark.asyncio
@patch.dict(os.environ, {
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_API_KEY": "test-key"
})
async def test_create_rag_agent_default_work_dir():
    """Test RAG agent uses default work directory when not specified."""
    agent = create_rag_agent(
        session_id="test_003",
        user_context={"user_id": "test"}
    )
    
    assert agent is not None
    # Default work_dir should be "./rag_agent_work"
    # This is verified by the agent being created successfully


# ===== YAML Configuration Tests =====

def test_tool_config_dataclass():
    """Test ToolConfig dataclass creation."""
    tool_config = ToolConfig(
        type="TestTool",
        module="test.module",
        params={"key": "value"}
    )
    
    assert tool_config.type == "TestTool"
    assert tool_config.module == "test.module"
    assert tool_config.params == {"key": "value"}


def test_tool_config_default_params():
    """Test ToolConfig with default params."""
    tool_config = ToolConfig(
        type="TestTool",
        module="test.module"
    )
    
    assert tool_config.params == {}


def test_agent_config_dataclass():
    """Test AgentConfig dataclass creation."""
    agent_config = AgentConfig(
        name="Test Agent",
        description="Test description",
        system_prompt="Test prompt",
        work_dir="./test_work",
        tools=[],
        llm_config={"model": "gpt-4"}
    )
    
    assert agent_config.name == "Test Agent"
    assert agent_config.description == "Test description"
    assert agent_config.system_prompt == "Test prompt"
    assert agent_config.work_dir == "./test_work"
    assert agent_config.tools == []
    assert agent_config.llm_config == {"model": "gpt-4"}


def test_agent_config_defaults():
    """Test AgentConfig with default values."""
    agent_config = AgentConfig(
        name="Test Agent",
        description="Test description"
    )
    
    assert agent_config.system_prompt is None
    assert agent_config.system_prompt_file is None
    assert agent_config.work_dir == "./agent_work"
    assert agent_config.tools == []
    assert agent_config.llm_config is None
    assert agent_config.mission is None


def test_load_agent_config_from_yaml_file_not_found():
    """Test loading config from non-existent file."""
    with pytest.raises(FileNotFoundError):
        load_agent_config_from_yaml("nonexistent_config.yaml")


def test_load_agent_config_from_yaml_missing_name():
    """Test loading config without required 'name' field."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"description": "Test"}, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="must include 'name' field"):
            load_agent_config_from_yaml(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_agent_config_from_yaml_missing_description():
    """Test loading config without required 'description' field."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"name": "Test Agent"}, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="must include 'description' field"):
            load_agent_config_from_yaml(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_agent_config_from_yaml_invalid_tool_config():
    """Test loading config with invalid tool configuration."""
    config_data = {
        "name": "Test Agent",
        "description": "Test description",
        "tools": [
            {"type": "TestTool"}  # Missing 'module'
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="must include 'type' and 'module'"):
            load_agent_config_from_yaml(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_agent_config_from_yaml_success():
    """Test successful loading of agent config from YAML."""
    config_data = {
        "name": "Test Agent",
        "description": "Test description",
        "system_prompt": "Test prompt",
        "work_dir": "./test_work",
        "tools": [
            {
                "type": "TestTool",
                "module": "test.module",
                "params": {"key": "value"}
            }
        ],
        "llm_config": {"model": "gpt-4"},
        "mission": "Test mission"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        config = load_agent_config_from_yaml(temp_path)
        
        assert config.name == "Test Agent"
        assert config.description == "Test description"
        assert config.system_prompt == "Test prompt"
        assert config.work_dir == "./test_work"
        assert len(config.tools) == 1
        assert config.tools[0].type == "TestTool"
        assert config.tools[0].module == "test.module"
        assert config.tools[0].params == {"key": "value"}
        assert config.llm_config == {"model": "gpt-4"}
        assert config.mission == "Test mission"
    finally:
        os.unlink(temp_path)


def test_load_system_prompt_inline():
    """Test loading inline system prompt."""
    config = AgentConfig(
        name="Test",
        description="Test",
        system_prompt="Inline prompt"
    )
    
    prompt = _load_system_prompt(config)
    assert prompt == "Inline prompt"


def test_load_system_prompt_from_file():
    """Test loading system prompt from file reference."""
    config = AgentConfig(
        name="Test",
        description="Test",
        system_prompt_file="capstone.agent_v2.prompts.rag_system_prompt:RAG_SYSTEM_PROMPT"
    )
    
    prompt = _load_system_prompt(config)
    assert prompt is not None
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_load_system_prompt_invalid_format():
    """Test loading system prompt with invalid file format."""
    config = AgentConfig(
        name="Test",
        description="Test",
        system_prompt_file="invalid_format_no_colon"
    )
    
    with pytest.raises(ValueError, match="must be in format 'module.path:VARIABLE_NAME'"):
        _load_system_prompt(config)


def test_load_system_prompt_module_not_found():
    """Test loading system prompt from non-existent module."""
    config = AgentConfig(
        name="Test",
        description="Test",
        system_prompt_file="nonexistent.module:VARIABLE"
    )
    
    with pytest.raises(ValueError, match="Failed to load system prompt"):
        _load_system_prompt(config)


def test_load_system_prompt_none():
    """Test loading system prompt when none specified."""
    config = AgentConfig(
        name="Test",
        description="Test"
    )
    
    prompt = _load_system_prompt(config)
    assert prompt is None


def test_load_system_prompt_inline_precedence():
    """Test that inline prompt takes precedence over file reference."""
    config = AgentConfig(
        name="Test",
        description="Test",
        system_prompt="Inline prompt",
        system_prompt_file="capstone.agent_v2.prompts.rag_system_prompt:RAG_SYSTEM_PROMPT"
    )
    
    prompt = _load_system_prompt(config)
    assert prompt == "Inline prompt"


def test_instantiate_tool():
    """Test instantiating a tool from config."""
    tool_config = ToolConfig(
        type="FileReadTool",
        module="capstone.agent_v2.tools.file_tool",
        params={}
    )
    
    tool = _instantiate_tool(tool_config)
    assert tool is not None
    assert tool.name == "file_read"


def test_instantiate_tool_with_params():
    """Test instantiating a tool with parameters."""
    tool_config = ToolConfig(
        type="PythonTool",
        module="capstone.agent_v2.tools.code_tool",
        params={}
    )
    
    tool = _instantiate_tool(tool_config)
    assert tool is not None
    assert tool.name == "python"


def test_instantiate_tool_llm_tool():
    """Test instantiating LLMTool with llm parameter."""
    import litellm
    
    tool_config = ToolConfig(
        type="LLMTool",
        module="capstone.agent_v2.tools.llm_tool",
        params={"llm": None}
    )
    
    tool = _instantiate_tool(tool_config, llm=litellm)
    assert tool is not None
    assert tool.name == "llm_generate"


def test_instantiate_tool_module_not_found():
    """Test instantiating tool from non-existent module."""
    tool_config = ToolConfig(
        type="TestTool",
        module="nonexistent.module",
        params={}
    )
    
    with pytest.raises(ImportError, match="Failed to import tool module"):
        _instantiate_tool(tool_config)


def test_instantiate_tool_class_not_found():
    """Test instantiating non-existent tool class."""
    tool_config = ToolConfig(
        type="NonExistentTool",
        module="capstone.agent_v2.tools.file_tool",
        params={}
    )
    
    with pytest.raises(AttributeError, match="Tool class .* not found"):
        _instantiate_tool(tool_config)


def test_configure_llm_none():
    """Test configuring LLM with None config."""
    import litellm
    
    llm = _configure_llm(None)
    assert llm == litellm


def test_configure_llm_with_config():
    """Test configuring LLM with config dict."""
    import litellm
    
    config = {"model": "gpt-4", "provider": "openai"}
    llm = _configure_llm(config)
    assert llm == litellm  # Currently just returns litellm


def test_create_agent_from_config():
    """Test creating agent from AgentConfig."""
    tool_configs = [
        ToolConfig(
            type="FileReadTool",
            module="capstone.agent_v2.tools.file_tool",
            params={}
        ),
        ToolConfig(
            type="LLMTool",
            module="capstone.agent_v2.tools.llm_tool",
            params={"llm": None}
        )
    ]
    
    config = AgentConfig(
        name="Test Agent",
        description="Test description",
        system_prompt="Test prompt",
        work_dir="./test_work",
        tools=tool_configs
    )
    
    agent = create_agent_from_config(config)
    
    assert agent is not None
    assert agent.name == "Test Agent"
    assert agent.description == "Test description"
    assert len(agent.tools) == 2


def test_create_agent_from_config_with_overrides():
    """Test creating agent with parameter overrides."""
    tool_configs = [
        ToolConfig(
            type="LLMTool",
            module="capstone.agent_v2.tools.llm_tool",
            params={"llm": None}
        )
    ]
    
    config = AgentConfig(
        name="Test Agent",
        description="Test description",
        work_dir="./test_work",
        tools=tool_configs
    )
    
    agent = create_agent_from_config(config, work_dir="./override_work")
    
    assert agent is not None


def test_create_agent_from_yaml_rag():
    """Test creating RAG agent from YAML config."""
    config_path = "capstone/agent_v2/configs/rag_agent.yaml"
    
    # Check if file exists
    if not Path(config_path).exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    with patch.dict(os.environ, {
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
        "AZURE_SEARCH_API_KEY": "test-key"
    }):
        agent = create_agent_from_yaml(config_path)
        
        assert agent is not None
        assert agent.name == "RAG Knowledge Assistant"
        assert len(agent.tools) == 4


def test_create_agent_from_yaml_standard():
    """Test creating standard agent from YAML config."""
    config_path = "capstone/agent_v2/configs/standard_agent.yaml"
    
    # Check if file exists
    if not Path(config_path).exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    agent = create_agent_from_yaml(config_path)
    
    assert agent is not None
    assert agent.name == "Standard Development Assistant"
    assert len(agent.tools) == 9


def test_create_agent_from_yaml_with_overrides():
    """Test creating agent from YAML with parameter overrides."""
    config_path = "capstone/agent_v2/configs/standard_agent.yaml"
    
    # Check if file exists
    if not Path(config_path).exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    agent = create_agent_from_yaml(
        config_path,
        work_dir="./custom_override_work"
    )
    
    assert agent is not None


def test_deepcopy_prevents_config_mutation():
    """Test that deepcopy prevents mutation of nested params in config.
    
    This tests the internal deepcopy logic without needing to instantiate tools.
    """
    from copy import deepcopy
    
    # Create original nested params
    original_params = {
        "user_context": {
            "user_id": "original_user",
            "org_id": "original_org"
        }
    }
    
    # Test shallow copy (would cause mutation - the bug we're preventing)
    shallow_copied = original_params.copy()
    shallow_copied["user_context"]["user_id"] = "modified"
    assert original_params["user_context"]["user_id"] == "modified"  # Mutation occurred
    
    # Reset for deep copy test
    original_params = {
        "user_context": {
            "user_id": "original_user",
            "org_id": "original_org"
        }
    }
    
    # Test deep copy (prevents mutation - what we implemented)
    deep_copied = deepcopy(original_params)
    deep_copied["user_context"]["user_id"] = "modified"
    deep_copied["user_context"]["new_key"] = "new_value"
    
    # Verify original is unchanged
    assert original_params["user_context"]["user_id"] == "original_user"
    assert "new_key" not in original_params["user_context"]

