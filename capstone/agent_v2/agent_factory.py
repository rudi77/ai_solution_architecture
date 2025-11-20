"""
Agent factory module for creating specialized agent instances.

This module provides builder functions for different agent types:
- create_standard_agent(): General-purpose agent with web, git, file, and shell tools
- create_rag_agent(): Specialized agent for document retrieval and knowledge search
- create_agent_from_yaml(): Create agents from YAML configuration files
"""

from copy import deepcopy
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
import structlog

from capstone.agent_v2.agent import Agent
from capstone.agent_v2.services.llm_service import LLMService
from capstone.agent_v2.tool import Tool
from capstone.agent_v2.tools.code_tool import PythonTool
from capstone.agent_v2.tools.file_tool import FileReadTool, FileWriteTool
from capstone.agent_v2.tools.git_tool import GitHubTool, GitTool
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.tools.shell_tool import PowerShellTool
from capstone.agent_v2.tools.web_tool import WebFetchTool, WebSearchTool


def create_llm_service(config_path: Optional[str] = None) -> LLMService:
    """
    Create LLMService instance with configuration.
    
    Args:
        config_path: Path to LLM config YAML file.
                     If None, uses default: "capstone/agent_v2/configs/llm_config.yaml"
    
    Returns:
        Configured LLMService instance
        
    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config is invalid
        
    Example:
        >>> llm_service = create_llm_service()
        >>> # Or with custom config:
        >>> llm_service = create_llm_service("custom_llm_config.yaml")
    """
    if config_path is None:
        # Default config path relative to this module
        module_dir = Path(__file__).parent
        config_path = module_dir / "configs" / "llm_config.yaml"
    else:
        config_path = Path(config_path)
    
    logger = structlog.get_logger()
    logger.info(
        "creating_llm_service",
        config_path=str(config_path)
    )
    
    try:
        llm_service = LLMService(config_path=str(config_path))
        return llm_service
    except FileNotFoundError:
        logger.error(
            "llm_config_not_found",
            config_path=str(config_path),
            hint="Ensure llm_config.yaml exists in configs directory"
        )
        raise
    except Exception as e:
        logger.error(
            "llm_service_creation_failed",
            error=str(e),
            config_path=str(config_path)
        )
        raise


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


def create_standard_agent(
    name: str,
    description: str,
    system_prompt: Optional[str] = None,
    mission: Optional[str] = None,
    work_dir: str = "./agent_work",
    llm_config_path: Optional[str] = None,
    llm_service: Optional[LLMService] = None,
    approval_policy: "ApprovalPolicy" = None
) -> Agent:
    """
    Create a general-purpose agent with standard tools.
    
    Standard tools include:
    - WebSearchTool: Search the web for information
    - WebFetchTool: Fetch content from URLs
    - PythonTool: Execute Python code
    - GitHubTool: Interact with GitHub repositories
    - GitTool: Perform git operations
    - FileReadTool: Read files from disk
    - FileWriteTool: Write files to disk
    - PowerShellTool: Execute PowerShell commands
    - LLMTool: Generate text using LLM
    
    Args:
        name: The name of the agent.
        description: The description of the agent.
        system_prompt: The system prompt for the agent (defaults to GENERIC_SYSTEM_PROMPT).
        mission: The mission for the agent.
        work_dir: The work directory for the agent (default: ./agent_work).
        llm_config_path: Path to LLM config (default: configs/llm_config.yaml)
        llm_service: LLMService instance (default: creates default service).
        approval_policy: Policy for handling approval requests (default: PROMPT).
    
    Returns:
        Agent instance configured with standard tools.
    
    Example:
        >>> agent = create_standard_agent(
        ...     name="Research Assistant",
        ...     description="Helps with research tasks",
        ...     mission="Find information about Python async patterns"
        ... )
    """
    from capstone.agent_v2.agent import ApprovalPolicy
    
    # Create LLMService if not provided
    if llm_service is None:
        llm_service = create_llm_service(config_path=llm_config_path)
    
    # Create standard tool set with LLMService
    tools = [
        WebSearchTool(),
        WebFetchTool(),
        PythonTool(),
        GitHubTool(),
        GitTool(),
        FileReadTool(),
        FileWriteTool(),
        PowerShellTool(),
        LLMTool(llm_service=llm_service, model_alias="main"),
    ]
    
    # Default approval policy
    if approval_policy is None:
        approval_policy = ApprovalPolicy.PROMPT
    
    return Agent.create_agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        mission=mission,
        tools=tools,
        work_dir=work_dir,
        llm_service=llm_service,
        approval_policy=approval_policy
    )


def create_rag_agent(
    session_id: str,
    user_context: Optional[Dict[str, Any]] = None,
    work_dir: Optional[str] = None,
    llm_config_path: Optional[str] = None,
    llm_service: Optional[LLMService] = None,
    approval_policy: "ApprovalPolicy" = None
) -> Agent:
    """
    Create an agent with RAG capabilities for document search and retrieval.
    
    RAG tools include:
    - SemanticSearchTool: Search documents using semantic similarity
    - ListDocumentsTool: List available documents
    - GetDocumentTool: Retrieve full document content
    - LLMTool: Generate text using LLM
    
    Args:
        session_id: Unique session identifier for the agent.
        user_context: User context for security filtering (user_id, org_id, scope).
        work_dir: Working directory for state and todolists (default: ./rag_agent_work).
        llm_config_path: Path to LLM config (default: configs/llm_config.yaml)
        llm_service: LLMService instance (default: creates default service).
        approval_policy: Policy for handling approval requests (default: PROMPT).
    
    Returns:
        Agent instance configured with RAG tools and system prompt.
    
    Example:
        >>> agent = create_rag_agent(
        ...     session_id="rag_session_001",
        ...     user_context={"user_id": "user123", "org_id": "org456", "scope": "shared"}
        ... )
        >>> async for event in agent.execute("What does the manual say about pumps?", session_id):
        ...     print(event)
    """
    from capstone.agent_v2.agent import ApprovalPolicy
    from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
    from capstone.agent_v2.tools.rag_list_documents_tool import ListDocumentsTool
    from capstone.agent_v2.tools.rag_get_document_tool import GetDocumentTool
    from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT
    
    # Create LLMService if not provided
    if llm_service is None:
        llm_service = create_llm_service(config_path=llm_config_path)
    
    # Create RAG tools with user context and LLMService
    rag_tools = [
        SemanticSearchTool(user_context=user_context),
        ListDocumentsTool(user_context=user_context),
        GetDocumentTool(user_context=user_context),
        LLMTool(llm_service=llm_service, model_alias="main"),
        PythonTool(),
        FileReadTool(),
        FileWriteTool(),
        PowerShellTool(),
    ]
    
    # Set default work directory
    if work_dir is None:
        work_dir = "./rag_agent_work"
    
    # Default approval policy
    if approval_policy is None:
        approval_policy = ApprovalPolicy.PROMPT
    
    return Agent.create_agent(
        name="RAG Knowledge Assistant",
        description="Agent with semantic search capabilities for enterprise documents",
        system_prompt=RAG_SYSTEM_PROMPT,
        mission=None,  # Mission will be set per execute() call
        tools=rag_tools,
        work_dir=work_dir,
        llm_service=llm_service,
        approval_policy=approval_policy
    )


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
    
    Raises:
        ValueError: If system_prompt_file format is invalid or cannot be loaded
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


def _instantiate_tool(tool_config: ToolConfig, llm_service: Optional[LLMService] = None) -> Tool:
    """
    Instantiate a tool from its configuration.
    
    Args:
        tool_config: ToolConfig with type, module, and params
        llm_service: LLMService instance to pass to LLMTool
    
    Returns:
        Instantiated Tool instance
    
    Raises:
        ImportError: If tool module cannot be imported
        AttributeError: If tool class not found in module
        TypeError: If tool cannot be instantiated with provided params
    """
    try:
        # Import the tool module
        module = importlib.import_module(tool_config.module)
        
        # Get the tool class
        tool_class = getattr(module, tool_config.type)
        
        # Handle special parameters
        params = tool_config.params.copy()
        
        # If tool is LLMTool, handle parameter injection
        if tool_config.type == 'LLMTool':
            # Remove deprecated 'llm' parameter if present
            params.pop('llm', None)
            
            # Add llm_service if not present
            if 'llm_service' not in params:
                if llm_service is None:
                    llm_service = create_llm_service()
                params['llm_service'] = llm_service
        
        # Instantiate the tool
        tool_instance = tool_class(**params)
        
        return tool_instance
        
    except ImportError as e:
        raise ImportError(f"Failed to import tool module {tool_config.module}: {e}")
    except AttributeError as e:
        raise AttributeError(f"Tool class {tool_config.type} not found in {tool_config.module}: {e}")
    except TypeError as e:
        raise TypeError(f"Failed to instantiate {tool_config.type} with params {params}: {e}")


def _create_llm_from_config(llm_config: Optional[Dict[str, Any]]) -> LLMService:
    """
    Create LLMService from agent config's llm_config section.
    
    Args:
        llm_config: LLM configuration from agent YAML:
            {
                "config_file": "configs/llm_config.yaml",  # Optional override
                "model_override": "powerful"  # Optional default model override
            }
    
    Returns:
        Configured LLMService instance
    
    Example config section in agent YAML:
        llm_config:
          config_file: "configs/llm_config.yaml"
          model_override: "powerful"
    """
    if llm_config is None:
        llm_config = {}
    
    # Get config file path (allow override)
    config_file = llm_config.get("config_file")
    
    # Create service
    llm_service = create_llm_service(config_path=config_file)
    
    # Apply model override if specified
    model_override = llm_config.get("model_override")
    if model_override:
        # Override default model in service
        llm_service.default_model = model_override
        
        logger = structlog.get_logger()
        logger.info(
            "llm_default_model_overridden",
            new_default=model_override
        )
    
    return llm_service


def create_agent_from_config(
    config: AgentConfig,
    llm_service: Optional[LLMService] = None,
    **override_params
) -> Agent:
    """
    Create an agent from a configuration object.
    
    Args:
        config: AgentConfig instance with agent configuration.
        llm_service: LLMService instance (default: creates from config or default service).
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
    # Create LLMService from config or use provided one
    if llm_service is None:
        llm_service = _create_llm_from_config(config.llm_config)
    
    # Load system prompt
    system_prompt = _load_system_prompt(config)
    
    # Apply parameter overrides to tool configs
    tools = []
    for tool_config in config.tools:
        # Deep copy params to prevent mutation of original config
        tool_params = deepcopy(tool_config.params)
        
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
        
        tool = _instantiate_tool(updated_tool_config, llm_service=llm_service)
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
        llm_service=llm_service
    )


def create_agent_from_yaml(
    config_path: str,
    llm_service: Optional[LLMService] = None,
    **override_params
) -> Agent:
    """
    Create an agent directly from a YAML file.
    
    Convenience function that combines load_agent_config_from_yaml()
    and create_agent_from_config().
    
    Args:
        config_path: Path to YAML configuration file.
        llm_service: LLMService instance (default: creates from config or default service).
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
    return create_agent_from_config(config, llm_service=llm_service, **override_params)

