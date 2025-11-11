# Agent Configuration Files

This directory contains YAML configuration files for creating agent instances.

## Overview

YAML-based agent configuration allows you to define agents without writing Python code. Each configuration file specifies:
- Agent metadata (name, description)
- System prompt (inline or from a Python module)
- Tools to include
- Working directory
- LLM configuration (optional)

## Configuration Schema

### Required Fields

- `name`: Agent name (string)
- `description`: Agent description (string)

### Optional Fields

- `system_prompt`: Inline system prompt text (string, multiline)
- `system_prompt_file`: Reference to Python module variable (format: `module.path:VARIABLE_NAME`)
- `work_dir`: Working directory for state and todolists (default: `./agent_work`)
- `tools`: List of tool configurations
- `llm_config`: LLM configuration dictionary
- `mission`: Default mission for the agent

### Tool Configuration

Each tool requires:
- `type`: Tool class name (e.g., `SemanticSearchTool`)
- `module`: Fully qualified Python module path (e.g., `capstone.agent_v2.tools.rag_semantic_search_tool`)
- `params`: Dictionary of parameters to pass to the tool constructor

## Example Configurations

### RAG Agent

```yaml
name: "RAG Knowledge Assistant"
description: "Agent with semantic search capabilities"

system_prompt_file: "capstone.agent_v2.prompts.rag_system_prompt:RAG_SYSTEM_PROMPT"

work_dir: "./rag_agent_work"

tools:
  - type: SemanticSearchTool
    module: capstone.agent_v2.tools.rag_semantic_search_tool
    params:
      user_context:
        user_id: "user123"
        org_id: "org456"
```

### Standard Agent

```yaml
name: "Development Assistant"
description: "General-purpose development agent"

system_prompt: |
  You are a helpful development assistant.
  
work_dir: "./agent_work"

tools:
  - type: WebSearchTool
    module: capstone.agent_v2.tools.web_tool
    params: {}
```

## Usage

### Python API

```python
from capstone.agent_v2.agent_factory import create_agent_from_yaml

# Simple usage
agent = create_agent_from_yaml("configs/rag_agent.yaml")

# With parameter overrides
agent = create_agent_from_yaml(
    "configs/rag_agent.yaml",
    user_context={"user_id": "user123", "org_id": "org456"},
    work_dir="./custom_work_dir"
)
```

### Creating Custom Configurations

1. **Copy an example config** as a starting point
2. **Modify the name and description**
3. **Choose your tools** from available tool modules
4. **Configure tool parameters** as needed
5. **Set the system prompt** (inline or file reference)

## Available Tools

### RAG Tools
- `SemanticSearchTool` - Semantic document search
- `ListDocumentsTool` - List available documents
- `GetDocumentTool` - Retrieve document content

### Standard Tools
- `WebSearchTool` - Web search
- `WebFetchTool` - Fetch web content
- `PythonTool` - Execute Python code
- `GitHubTool` - GitHub operations
- `GitTool` - Git operations
- `FileReadTool` - Read files
- `FileWriteTool` - Write files
- `PowerShellTool` - PowerShell commands
- `LLMTool` - LLM text generation

## Parameter Overrides

Runtime parameters can override config values:

```python
agent = create_agent_from_yaml(
    "configs/rag_agent.yaml",
    user_context={"user_id": "runtime_user"},  # Overrides tool user_context
    work_dir="./runtime_work"  # Overrides config work_dir
)
```

For nested parameters like `user_context`, the override values are merged with the config values.

## Security Notes

- Use `yaml.safe_load()` for security (already implemented)
- Never commit API keys or sensitive data in config files
- Use environment variables for secrets
- Validate tool parameters before instantiation

## Troubleshooting

### FileNotFoundError
- Check that the config file path is correct
- Use absolute paths or paths relative to working directory

### ImportError
- Verify tool module paths are correct
- Ensure all required packages are installed

### ValueError (invalid config)
- Check that required fields (name, description) are present
- Verify tool configs have both `type` and `module`
- Ensure system_prompt_file uses `module:variable` format

## Best Practices

1. **Use descriptive names** for your agents
2. **Comment your configs** to explain tool choices
3. **Version control** your configs
4. **Test configs** after creation
5. **Use file references** for reusable system prompts
6. **Keep tool lists minimal** - only include what's needed
7. **Document custom parameters** in comments

