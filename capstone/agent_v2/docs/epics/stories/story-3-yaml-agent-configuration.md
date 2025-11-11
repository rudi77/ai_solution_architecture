# Story 3: Implement YAML-Based Agent Configuration

**Epic:** Generalize Agent Factory Pattern - Brownfield Enhancement  
**Story ID:** AGENT-003  
**Story Type:** Feature Development  
**Priority:** Medium  
**Estimated Effort:** 6 hours

## User Story

**As a** developer or system administrator  
**I want** to define agent configurations in YAML files  
**So that** I can create and customize agents without writing Python code and easily manage different agent configurations

## Background

Currently, all agent configurations are hardcoded in Python. To create a new agent type or modify an existing one, you must write Python code. YAML-based configuration would enable:
- Non-developers to configure agents
- Version-controlled agent configurations
- Easy experimentation with different tool combinations
- Deployment flexibility (different configs for dev/staging/prod)

## Goal

Implement a complete YAML-based agent configuration system that:
1. Defines a clear YAML schema for agent configuration
2. Loads and validates YAML configuration files
3. Instantiates agents from YAML configuration
4. Handles tool instantiation with parameters
5. Supports both inline and file-based system prompts

## Proposed Implementation

### YAML Configuration Schema

```yaml
# Example: configs/rag_agent.yaml
name: "RAG Knowledge Assistant"
description: "Agent with semantic search capabilities for enterprise documents"

# System prompt can be inline or reference a file
system_prompt: |
  You are a RAG agent specialized in document retrieval.
  Use semantic search to find relevant information.

# OR reference a Python module with the prompt
system_prompt_file: "capstone.agent_v2.prompts.rag_system_prompt:RAG_SYSTEM_PROMPT"

# Working directory for agent state and todolists
work_dir: "./rag_agent_work"

# Tool configuration
tools:
  - type: SemanticSearchTool
    module: capstone.agent_v2.tools.rag_semantic_search_tool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: ListDocumentsTool
    module: capstone.agent_v2.tools.rag_list_documents_tool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: GetDocumentTool
    module: capstone.agent_v2.tools.rag_get_document_tool
    params:
      user_context:
        user_id: "default_user"
        org_id: "default_org"
        scope: "shared"
  
  - type: LLMTool
    module: capstone.agent_v2.tools.llm_tool
    params:
      llm: null  # Will use default

# LLM configuration (optional)
llm_config:
  provider: "litellm"
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"  # Environment variable name
```

### Enhanced agent_factory.py

Add to `capstone/agent_v2/agent_factory.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml
import importlib
import os


@dataclass
class ToolConfig:
    """Configuration for a single tool."""
    type: str  # Tool class name
    module: str  # Python module path
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Agent configuration loaded from YAML."""
    name: str
    description: str
    system_prompt: Optional[str] = None
    system_prompt_file: Optional[str] = None  # module:variable format
    work_dir: str = "./agent_work"
    tools: List[ToolConfig] = field(default_factory=list)
    llm_config: Optional[Dict[str, Any]] = None
    mission: Optional[str] = None


def load_agent_config_from_yaml(config_path: str) -> AgentConfig:
    """
    Load agent configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file.
    
    Returns:
        AgentConfig instance with loaded configuration.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If configuration is invalid.
    
    Example:
        >>> config = load_agent_config_from_yaml("configs/rag_agent.yaml")
        >>> agent = create_agent_from_config(config)
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f)
    
    # Validate required fields
    if 'name' not in yaml_data:
        raise ValueError("Configuration must include 'name' field")
    if 'description' not in yaml_data:
        raise ValueError("Configuration must include 'description' field")
    
    # Parse tool configurations
    tool_configs = []
    for tool_data in yaml_data.get('tools', []):
        if 'type' not in tool_data or 'module' not in tool_data:
            raise ValueError(f"Tool configuration must include 'type' and 'module': {tool_data}")
        
        tool_configs.append(ToolConfig(
            type=tool_data['type'],
            module=tool_data['module'],
            params=tool_data.get('params', {})
        ))
    
    # Create AgentConfig
    config = AgentConfig(
        name=yaml_data['name'],
        description=yaml_data['description'],
        system_prompt=yaml_data.get('system_prompt'),
        system_prompt_file=yaml_data.get('system_prompt_file'),
        work_dir=yaml_data.get('work_dir', './agent_work'),
        tools=tool_configs,
        llm_config=yaml_data.get('llm_config'),
        mission=yaml_data.get('mission')
    )
    
    return config


def _load_system_prompt(config: AgentConfig) -> Optional[str]:
    """
    Load system prompt from config.
    
    Handles both inline prompts and file references.
    File references use format: "module.path:VARIABLE_NAME"
    
    Args:
        config: AgentConfig instance
    
    Returns:
        System prompt string or None
    """
    # Inline prompt takes precedence
    if config.system_prompt:
        return config.system_prompt
    
    # Load from file reference
    if config.system_prompt_file:
        try:
            # Parse module:variable format
            if ':' not in config.system_prompt_file:
                raise ValueError(
                    f"system_prompt_file must be in format 'module.path:VARIABLE_NAME', "
                    f"got: {config.system_prompt_file}"
                )
            
            module_path, variable_name = config.system_prompt_file.split(':', 1)
            module = importlib.import_module(module_path)
            prompt = getattr(module, variable_name)
            
            return prompt
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load system prompt from {config.system_prompt_file}: {e}")
    
    return None


def _instantiate_tool(tool_config: ToolConfig, llm=None) -> Tool:
    """
    Instantiate a tool from its configuration.
    
    Args:
        tool_config: ToolConfig with type, module, and params
        llm: LLM instance to pass to tools that need it
    
    Returns:
        Instantiated Tool instance
    
    Raises:
        ImportError: If tool module cannot be imported
        AttributeError: If tool class not found in module
    """
    try:
        # Import the tool module
        module = importlib.import_module(tool_config.module)
        
        # Get the tool class
        tool_class = getattr(module, tool_config.type)
        
        # Handle special parameters
        params = tool_config.params.copy()
        
        # If tool is LLMTool and llm is None in params, use provided llm
        if tool_config.type == 'LLMTool' and params.get('llm') is None:
            params['llm'] = llm
        
        # Instantiate the tool
        tool_instance = tool_class(**params)
        
        return tool_instance
        
    except ImportError as e:
        raise ImportError(f"Failed to import tool module {tool_config.module}: {e}")
    except AttributeError as e:
        raise AttributeError(f"Tool class {tool_config.type} not found in {tool_config.module}: {e}")
    except TypeError as e:
        raise TypeError(f"Failed to instantiate {tool_config.type} with params {params}: {e}")


def _configure_llm(llm_config: Optional[Dict[str, Any]]):
    """
    Configure LLM from configuration.
    
    Args:
        llm_config: Dictionary with LLM configuration
    
    Returns:
        Configured LLM instance (currently returns litellm)
    """
    if llm_config is None:
        return litellm
    
    # For now, just return litellm
    # Future: Could configure model, API keys, etc.
    # Example: litellm.model = llm_config.get('model', 'gpt-4o-mini')
    
    return litellm


def create_agent_from_config(
    config: AgentConfig,
    llm=None,
    **override_params
) -> Agent:
    """
    Create an agent from a configuration object.
    
    Args:
        config: AgentConfig instance with agent configuration.
        llm: Optional LLM instance (overrides config.llm_config).
        **override_params: Additional parameters to override config values
                          (e.g., user_context, work_dir).
    
    Returns:
        Agent instance configured according to the config.
    
    Example:
        >>> config = load_agent_config_from_yaml("configs/rag_agent.yaml")
        >>> agent = create_agent_from_config(
        ...     config,
        ...     user_context={"user_id": "user123"}
        ... )
    """
    # Configure LLM
    if llm is None:
        llm = _configure_llm(config.llm_config)
    
    # Load system prompt
    system_prompt = _load_system_prompt(config)
    
    # Apply parameter overrides to tool configs
    tools = []
    for tool_config in config.tools:
        # Deep copy params and apply overrides
        tool_params = tool_config.params.copy()
        
        # Apply overrides (e.g., user_context)
        for key, value in override_params.items():
            if key in tool_params:
                # Merge dictionaries for nested params like user_context
                if isinstance(tool_params[key], dict) and isinstance(value, dict):
                    tool_params[key].update(value)
                else:
                    tool_params[key] = value
        
        # Create a new ToolConfig with updated params
        updated_tool_config = ToolConfig(
            type=tool_config.type,
            module=tool_config.module,
            params=tool_params
        )
        
        tool = _instantiate_tool(updated_tool_config, llm=llm)
        tools.append(tool)
    
    # Get work_dir (override takes precedence)
    work_dir = override_params.get('work_dir', config.work_dir)
    
    # Create agent using the factory
    return Agent.create_agent(
        name=config.name,
        description=config.description,
        system_prompt=system_prompt,
        mission=config.mission,
        tools=tools,
        work_dir=work_dir,
        llm=llm
    )


def create_agent_from_yaml(
    config_path: str,
    llm=None,
    **override_params
) -> Agent:
    """
    Create an agent directly from a YAML file.
    
    Convenience function that combines load_agent_config_from_yaml()
    and create_agent_from_config().
    
    Args:
        config_path: Path to YAML configuration file.
        llm: Optional LLM instance.
        **override_params: Parameters to override config values.
    
    Returns:
        Agent instance configured from YAML.
    
    Example:
        >>> agent = create_agent_from_yaml(
        ...     "configs/rag_agent.yaml",
        ...     user_context={"user_id": "user123", "org_id": "org456"}
        ... )
    """
    config = load_agent_config_from_yaml(config_path)
    return create_agent_from_config(config, llm=llm, **override_params)
```

## Acceptance Criteria

### Configuration Schema

- [ ] YAML schema defined and documented
- [ ] Supports inline system prompts
- [ ] Supports file-based system prompts (module:variable format)
- [ ] Supports tool configuration with type, module, and params
- [ ] Supports LLM configuration (optional)
- [ ] Supports work_dir configuration
- [ ] Supports mission configuration (optional)

### Data Classes

- [ ] `AgentConfig` dataclass created with all fields
- [ ] `ToolConfig` dataclass created with type, module, params
- [ ] Both dataclasses have proper type hints
- [ ] Default values work correctly

### YAML Loading

- [ ] `load_agent_config_from_yaml()` function implemented
- [ ] Validates required fields (name, description)
- [ ] Parses tool configurations correctly
- [ ] Returns AgentConfig instance
- [ ] Raises appropriate errors for invalid configs
- [ ] Handles missing optional fields gracefully

### System Prompt Loading

- [ ] `_load_system_prompt()` handles inline prompts
- [ ] `_load_system_prompt()` loads from file reference (module:variable)
- [ ] Returns None if no prompt specified
- [ ] Raises clear error for invalid file references

### Tool Instantiation

- [ ] `_instantiate_tool()` dynamically imports tool module
- [ ] Gets tool class from module
- [ ] Passes parameters to tool constructor
- [ ] Handles LLMTool special case (llm parameter)
- [ ] Raises clear errors for import/instantiation failures

### Agent Creation from Config

- [ ] `create_agent_from_config()` creates agent from AgentConfig
- [ ] Instantiates all tools from config
- [ ] Loads system prompt correctly
- [ ] Supports parameter overrides (user_context, work_dir)
- [ ] Calls `Agent.create_agent()` with correct parameters

### Convenience Function

- [ ] `create_agent_from_yaml()` combines load and create steps
- [ ] Accepts config path and returns Agent
- [ ] Supports all override parameters

### Example Configurations

- [ ] `configs/rag_agent.yaml` created and works
- [ ] `configs/standard_agent.yaml` created and works
- [ ] Both configs are well-documented with comments

### Documentation

- [ ] README updated with YAML configuration examples
- [ ] Docstrings complete for all new functions
- [ ] YAML schema documented

## Technical Implementation Details

### Files to Create

1. **`capstone/agent_v2/configs/rag_agent.yaml`** - Example RAG agent config
2. **`capstone/agent_v2/configs/standard_agent.yaml`** - Example standard agent config
3. **`capstone/agent_v2/configs/README.md`** - Configuration documentation

### Files to Modify

1. **`capstone/agent_v2/agent_factory.py`**
   - Add imports: `yaml`, `importlib`, `dataclasses`
   - Add dataclasses: `AgentConfig`, `ToolConfig`
   - Add functions: `load_agent_config_from_yaml`, `_load_system_prompt`, `_instantiate_tool`, `_configure_llm`, `create_agent_from_config`, `create_agent_from_yaml`

2. **`capstone/agent_v2/README.md`**
   - Add section on YAML configuration
   - Add examples

### Dependencies

Add to `pyproject.toml` (if not already present):
```toml
[project]
dependencies = [
    "pyyaml>=6.0",
    # ... existing dependencies
]
```

### Implementation Steps

1. **Add dataclasses to agent_factory.py**
   - Define `ToolConfig`
   - Define `AgentConfig`

2. **Implement YAML loading**
   - `load_agent_config_from_yaml()`
   - Add validation

3. **Implement helper functions**
   - `_load_system_prompt()`
   - `_instantiate_tool()`
   - `_configure_llm()`

4. **Implement agent creation**
   - `create_agent_from_config()`
   - `create_agent_from_yaml()`

5. **Create example configs**
   - `configs/rag_agent.yaml`
   - `configs/standard_agent.yaml`
   - `configs/README.md`

6. **Update documentation**
   - Update main README with examples
   - Add docstrings

## Testing Strategy

### Unit Tests

Add to `tests/test_agent_factory.py`:

```python
def test_load_agent_config_from_yaml():
    """Test loading agent config from YAML."""
    config = load_agent_config_from_yaml("configs/rag_agent.yaml")
    
    assert config.name == "RAG Knowledge Assistant"
    assert config.description is not None
    assert len(config.tools) >= 3
    assert config.work_dir == "./rag_agent_work"


def test_create_agent_from_yaml():
    """Test creating agent from YAML config."""
    agent = create_agent_from_yaml("configs/rag_agent.yaml")
    
    assert agent.name == "RAG Knowledge Assistant"
    assert len(agent.tools) >= 3


def test_yaml_config_with_overrides():
    """Test YAML config with parameter overrides."""
    agent = create_agent_from_yaml(
        "configs/rag_agent.yaml",
        user_context={"user_id": "override_user"}
    )
    
    # Verify user_context was overridden in tools
    # (Would need to check tool params)
    assert agent is not None


def test_invalid_yaml_config():
    """Test error handling for invalid config."""
    with pytest.raises(ValueError):
        load_agent_config_from_yaml("configs/invalid.yaml")
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_yaml_agent_execution():
    """Test that YAML-configured agent can execute."""
    agent = create_agent_from_yaml("configs/standard_agent.yaml")
    
    # Test agent execution (basic smoke test)
    assert agent is not None
    assert len(agent.tools) > 0
```

### Manual Testing

```python
# Test creating agent from YAML
from capstone.agent_v2.agent_factory import create_agent_from_yaml

agent = create_agent_from_yaml(
    "capstone/agent_v2/configs/rag_agent.yaml",
    user_context={"user_id": "test_user", "org_id": "test_org"}
)

print(f"Agent: {agent.name}")
print(f"Tools: {[t.name for t in agent.tools]}")
print(f"Description: {agent.description}")
```

## Dependencies

### Depends On
- **Story 1**: Agent.create_agent() with tools parameter
- **Story 2**: agent_factory module exists

### Blocks
- None (this is the final story)

### External Dependencies
- `pyyaml` library for YAML parsing

## Definition of Done

- [ ] All dataclasses implemented and tested
- [ ] YAML loading function works correctly
- [ ] Tool instantiation from config works
- [ ] System prompt loading works (inline and file)
- [ ] Agent creation from config works
- [ ] Two example YAML configs created and working
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No linting errors
- [ ] Code reviewed
- [ ] Can create RAG agent from YAML via CLI or Python

## Rollback Plan

If issues arise:
1. Git revert the commit
2. Remove YAML config files
3. Factory module still works without YAML functionality

## Usage Examples

### Creating Agent from YAML

```python
from capstone.agent_v2.agent_factory import create_agent_from_yaml

# Simple creation
agent = create_agent_from_yaml("configs/rag_agent.yaml")

# With overrides
agent = create_agent_from_yaml(
    "configs/rag_agent.yaml",
    user_context={"user_id": "user123", "org_id": "org456"},
    work_dir="./custom_work_dir"
)
```

### YAML Configuration Examples

See `configs/` directory for complete examples.

## Notes

- YAML configs are optional - programmatic creation still works
- Tool parameters in YAML can be overridden at runtime
- System prompts can be inline (for simple cases) or file-based (for reusability)
- Tool module paths must be fully qualified Python module paths
- Consider adding JSON Schema validation in future iterations

## Verification Checklist

Before marking this story complete:

- [ ] YAML files parse correctly
- [ ] Can create both RAG and standard agents from YAML
- [ ] Parameter overrides work
- [ ] Error messages are clear and helpful
- [ ] All tests pass
- [ ] Documentation is complete
- [ ] Example configs work out of the box
- [ ] No security issues (YAML safe_load used)

---

**Created:** 2025-11-11  
**Status:** Ready for Development (blocked by Story 1 & 2)  
**Assignee:** TBD  
**Labels:** feature, agent-factory, configuration, yaml

