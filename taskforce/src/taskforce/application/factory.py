"""
Application Layer - Agent Factory

This module provides dependency injection factory for creating Agent instances
with different infrastructure adapters based on configuration profiles.

The factory adapts logic from Agent V2's agent_factory.py and Agent.create_agent()
to work with the new Clean Architecture structure.

Key Responsibilities:
- Load configuration profiles (dev/staging/prod)
- Instantiate infrastructure adapters (state managers, LLM providers, tools)
- Wire dependencies into core domain Agent
- Support specialist profiles (generic, coding, rag) with layered prompts
- Inject appropriate toolsets based on specialist profile
"""

import os
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from taskforce.core.domain.agent import Agent
from taskforce.core.interfaces.llm import LLMProviderProtocol
from taskforce.infrastructure.persistence.file_todolist import FileTodoListManager
from taskforce.core.interfaces.state import StateManagerProtocol
from taskforce.core.interfaces.tools import ToolProtocol


class AgentFactory:
    """
    Factory for creating agents with dependency injection.

    Wires core domain objects with infrastructure adapters based on
    configuration profiles (dev/staging/prod).

    The factory follows the Agent V2 pattern but adapts it to Clean Architecture:
    - Reads YAML configuration profiles
    - Instantiates appropriate infrastructure adapters
    - Injects dependencies into core Agent
    - Supports both generic and RAG agent types
    """

    def __init__(self, config_dir: str = "configs"):
        """
        Initialize AgentFactory with configuration directory.

        Args:
            config_dir: Path to directory containing profile YAML files
        """
        self.config_dir = Path(config_dir)
        self.logger = structlog.get_logger().bind(component="agent_factory")

    async def create_agent(
        self,
        profile: str = "dev",
        specialist: Optional[str] = None,
        mission: Optional[str] = None,
        work_dir: Optional[str] = None,
    ) -> Agent:
        """
        Create agent with specified specialist profile.

        Creates an agent with the autonomous kernel prompt plus specialist-specific
        instructions and toolset. The specialist profile determines both the
        additional prompt instructions and the available tools.

        Specialist Profiles:
        - "generic": Full toolset with kernel prompt only (default)
        - "coding": FileReadTool, FileWriteTool, PowerShellTool, AskUserTool
        - "rag": SemanticSearchTool, ListDocumentsTool, GetDocumentTool, AskUserTool

        Args:
            profile: Configuration profile name (dev/staging/prod/coding_dev/rag_dev)
            specialist: Specialist profile override. If None, reads from config YAML.
            mission: Optional mission description
            work_dir: Optional override for work directory

        Returns:
            Agent instance with injected dependencies

        Raises:
            FileNotFoundError: If profile YAML not found
            ValueError: If configuration or specialist is invalid

        Example:
            >>> factory = AgentFactory()
            >>> # Load specialist from config
            >>> agent = await factory.create_agent(profile="coding_dev")
            >>> # Or override specialist
            >>> agent = await factory.create_agent(profile="dev", specialist="coding")
        """
        config = self._load_profile(profile)

        # Override work_dir if provided
        if work_dir:
            config.setdefault("persistence", {})["work_dir"] = work_dir

        # Determine specialist: parameter > config > default
        effective_specialist = specialist or config.get("specialist", "generic")

        self.logger.info(
            "creating_agent",
            profile=profile,
            specialist=effective_specialist,
            work_dir=config.get("persistence", {}).get("work_dir", ".taskforce"),
        )

        # Instantiate infrastructure adapters
        state_manager = self._create_state_manager(config)
        llm_provider = self._create_llm_provider(config)

        # Select tools based on specialist profile
        if effective_specialist in ("coding", "rag"):
            tools = self._create_specialist_tools(
                effective_specialist, config, llm_provider
            )
            mcp_contexts = []
        else:
            # Generic: use config-based tools or defaults
            tools = self._create_native_tools(config, llm_provider)
            # Load MCP tools if configured
            mcp_tools, mcp_contexts = await self._create_mcp_tools(config)
            tools.extend(mcp_tools)

        todolist_manager = self._create_todolist_manager(config, llm_provider)
        system_prompt = self._assemble_system_prompt(effective_specialist)

        # Create domain agent with injected dependencies
        agent = Agent(
            state_manager=state_manager,
            llm_provider=llm_provider,
            tools=tools,
            todolist_manager=todolist_manager,
            system_prompt=system_prompt,
        )

        # Store MCP contexts on agent for lifecycle management
        agent._mcp_contexts = mcp_contexts

        return agent

    async def create_rag_agent(
        self,
        profile: str = "dev",
        user_context: Optional[dict[str, Any]] = None,
        work_dir: Optional[str] = None,
    ) -> Agent:
        """
        Create RAG-enabled agent for document retrieval.

        Creates an agent with RAG tools (semantic search, list documents, get document)
        in addition to standard tools. Uses RAG-specific system prompt.

        Args:
            profile: Configuration profile name (dev/staging/prod)
            user_context: User context for security filtering (user_id, org_id, scope)
            work_dir: Optional override for work directory

        Returns:
            Agent instance with RAG capabilities

        Raises:
            FileNotFoundError: If profile YAML not found
            ValueError: If RAG configuration is missing or invalid

        Example:
            >>> factory = AgentFactory()
            >>> agent = factory.create_rag_agent(
            ...     profile="dev",
            ...     user_context={"user_id": "user123", "org_id": "org456"}
            ... )
            >>> result = await agent.execute("What does the manual say?", "session-123")
        """
        config = self._load_profile(profile)

        # Override work_dir if provided
        if work_dir:
            config.setdefault("persistence", {})["work_dir"] = work_dir

        self.logger.info(
            "creating_rag_agent",
            profile=profile,
            agent_type="rag",
            work_dir=config.get("persistence", {}).get("work_dir", ".taskforce"),
            has_user_context=user_context is not None,
        )

        # Instantiate infrastructure adapters
        state_manager = self._create_state_manager(config)
        llm_provider = self._create_llm_provider(config)

        # RAG agent tools are now specified in config (includes RAG + native tools)
        # user_context is injected into RAG tools
        tools = self._create_native_tools(config, llm_provider, user_context=user_context)
        
        # Load MCP tools if configured
        mcp_tools, mcp_contexts = await self._create_mcp_tools(config)
        tools.extend(mcp_tools)

        todolist_manager = self._create_todolist_manager(config, llm_provider)
        system_prompt = self._load_system_prompt("rag")

        agent = Agent(
            state_manager=state_manager,
            llm_provider=llm_provider,
            tools=tools,
            todolist_manager=todolist_manager,
            system_prompt=system_prompt,
        )
        
        # Store MCP contexts on agent for lifecycle management
        agent._mcp_contexts = mcp_contexts
        
        return agent

    def _load_profile(self, profile: str) -> dict:
        """
        Load configuration profile from YAML file.

        Args:
            profile: Profile name (dev/staging/prod)

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If profile YAML not found
        """
        profile_path = self.config_dir / f"{profile}.yaml"

        if not profile_path.exists():
            self.logger.error(
                "profile_not_found",
                profile=profile,
                path=str(profile_path),
                hint="Ensure profile YAML exists in configs directory",
            )
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        with open(profile_path) as f:
            config = yaml.safe_load(f)

        self.logger.debug("profile_loaded", profile=profile, config_keys=list(config.keys()))
        return config

    def _create_state_manager(self, config: dict) -> StateManagerProtocol:
        """
        Create state manager based on configuration.

        Args:
            config: Configuration dictionary

        Returns:
            StateManager implementation (file-based or database)
        """
        persistence_config = config.get("persistence", {})
        persistence_type = persistence_config.get("type", "file")

        if persistence_type == "file":
            from taskforce.infrastructure.persistence.file_state import FileStateManager

            work_dir = persistence_config.get("work_dir", ".taskforce")
            return FileStateManager(work_dir=work_dir)

        elif persistence_type == "database":
            from taskforce.infrastructure.persistence.db_state import DbStateManager

            # Get database URL from config or environment
            db_url_env = persistence_config.get("db_url_env", "DATABASE_URL")
            db_url = os.getenv(db_url_env)

            if not db_url:
                raise ValueError(
                    f"Database URL not found in environment variable: {db_url_env}"
                )

            return DbStateManager(db_url=db_url)

        else:
            raise ValueError(f"Unknown persistence type: {persistence_type}")

    def _create_llm_provider(self, config: dict) -> LLMProviderProtocol:
        """
        Create LLM provider based on configuration.

        Args:
            config: Configuration dictionary

        Returns:
            LLM provider implementation (OpenAI)
        """
        from taskforce.infrastructure.llm.openai_service import OpenAIService

        llm_config = config.get("llm", {})
        config_path = llm_config.get("config_path", "configs/llm_config.yaml")

        return OpenAIService(config_path=config_path)

    def _create_native_tools(
        self, config: dict, llm_provider: LLMProviderProtocol, user_context: Optional[dict[str, Any]] = None
    ) -> list[ToolProtocol]:
        """
        Create native tools from configuration.

        Args:
            config: Configuration dictionary
            llm_provider: LLM provider for LLMTool
            user_context: Optional user context for RAG tools

        Returns:
            List of native tool instances
        """
        tools_config = config.get("tools", [])
        
        if not tools_config:
            # Fallback to default tool set if no config provided
            return self._create_default_tools(llm_provider)
        
        tools = []
        for tool_spec in tools_config:
            tool = self._instantiate_tool(tool_spec, llm_provider, user_context=user_context)
            if tool:
                tools.append(tool)
        
        return tools
    
    async def _create_mcp_tools(self, config: dict) -> tuple[list[ToolProtocol], list[Any]]:
        """
        Create MCP tools from configuration.

        Connects to configured MCP servers (stdio or SSE), fetches available tools,
        and wraps them in MCPToolWrapper to conform to ToolProtocol.

        IMPORTANT: Returns both tools and client context managers that must be kept alive.
        The caller is responsible for managing the lifecycle of these connections.

        Args:
            config: Configuration dictionary containing mcp_servers list

        Returns:
            Tuple of (list of MCP tool wrappers, list of client context managers)

        Example config:
            mcp_servers:
              - type: stdio
                command: python
                args: ["server.py"]
                env: {"API_KEY": "value"}
              - type: sse
                url: http://localhost:8000/sse
        """
        from taskforce.infrastructure.tools.mcp.client import MCPClient
        from taskforce.infrastructure.tools.mcp.wrapper import MCPToolWrapper

        mcp_servers_config = config.get("mcp_servers", [])
        
        if not mcp_servers_config:
            self.logger.debug("no_mcp_servers_configured")
            return [], []
        
        mcp_tools = []
        client_contexts = []
        
        for server_config in mcp_servers_config:
            server_type = server_config.get("type")
            
            try:
                if server_type == "stdio":
                    # Local stdio server
                    command = server_config.get("command")
                    args = server_config.get("args", [])
                    env = server_config.get("env")
                    
                    if not command:
                        self.logger.warning(
                            "mcp_server_missing_command",
                            server_config=server_config,
                            hint="stdio server requires 'command' field",
                        )
                        continue
                    
                    self.logger.info(
                        "connecting_to_mcp_server",
                        server_type="stdio",
                        command=command,
                        args=args,
                    )
                    
                    # Create context manager but don't enter yet
                    ctx = MCPClient.create_stdio(command, args, env)
                    client = await ctx.__aenter__()
                    client_contexts.append(ctx)
                    
                    tools_list = await client.list_tools()
                    
                    self.logger.info(
                        "mcp_server_connected",
                        server_type="stdio",
                        command=command,
                        tools_count=len(tools_list),
                        tool_names=[t["name"] for t in tools_list],
                    )
                    
                    # Wrap each tool
                    for tool_def in tools_list:
                        wrapper = MCPToolWrapper(client, tool_def)
                        mcp_tools.append(wrapper)
                
                elif server_type == "sse":
                    # Remote SSE server
                    url = server_config.get("url")
                    
                    if not url:
                        self.logger.warning(
                            "mcp_server_missing_url",
                            server_config=server_config,
                            hint="sse server requires 'url' field",
                        )
                        continue
                    
                    self.logger.info(
                        "connecting_to_mcp_server",
                        server_type="sse",
                        url=url,
                    )
                    
                    # Create context manager but don't enter yet
                    ctx = MCPClient.create_sse(url)
                    client = await ctx.__aenter__()
                    client_contexts.append(ctx)
                    
                    tools_list = await client.list_tools()
                    
                    self.logger.info(
                        "mcp_server_connected",
                        server_type="sse",
                        url=url,
                        tools_count=len(tools_list),
                        tool_names=[t["name"] for t in tools_list],
                    )
                    
                    # Wrap each tool
                    for tool_def in tools_list:
                        wrapper = MCPToolWrapper(client, tool_def)
                        mcp_tools.append(wrapper)
                
                else:
                    self.logger.warning(
                        "unknown_mcp_server_type",
                        server_type=server_type,
                        hint="Supported types: 'stdio', 'sse'",
                    )
            
            except Exception as e:
                # Log error but don't crash - graceful degradation
                self.logger.warning(
                    "mcp_server_connection_failed",
                    server_type=server_type,
                    server_config=server_config,
                    error=str(e),
                    error_type=type(e).__name__,
                    hint="Agent will continue without this MCP server",
                )
        
        return mcp_tools, client_contexts
    
    def _create_default_tools(self, llm_provider: LLMProviderProtocol) -> list[ToolProtocol]:
        """
        Create default tool set (fallback when no config provided).

        Args:
            llm_provider: LLM provider for LLMTool

        Returns:
            List of default tool instances
        """
        from taskforce.infrastructure.tools.native.ask_user_tool import AskUserTool
        from taskforce.infrastructure.tools.native.file_tools import (
            FileReadTool,
            FileWriteTool,
        )
        from taskforce.infrastructure.tools.native.git_tools import GitHubTool, GitTool
        from taskforce.infrastructure.tools.native.llm_tool import LLMTool
        from taskforce.infrastructure.tools.native.python_tool import PythonTool
        from taskforce.infrastructure.tools.native.shell_tool import PowerShellTool
        from taskforce.infrastructure.tools.native.web_tools import (
            WebFetchTool,
            WebSearchTool,
        )

        # Standard tool set matching Agent V2
        return [
            WebSearchTool(),
            WebFetchTool(),
            PythonTool(),
            GitHubTool(),
            GitTool(),
            FileReadTool(),
            FileWriteTool(),
            PowerShellTool(),
            LLMTool(llm_service=llm_provider),
            AskUserTool(),
        ]

    def _create_specialist_tools(
        self,
        specialist: str,
        config: dict,
        llm_provider: LLMProviderProtocol,
        user_context: Optional[dict[str, Any]] = None,
    ) -> list[ToolProtocol]:
        """
        Create tools specific to a specialist profile.

        Each specialist profile has a focused toolset:
        - coding: FileReadTool, FileWriteTool, PowerShellTool, AskUserTool
        - rag: SemanticSearchTool, ListDocumentsTool, GetDocumentTool, AskUserTool

        Args:
            specialist: Specialist profile ("coding" or "rag")
            config: Configuration dictionary (for RAG tools configuration)
            llm_provider: LLM provider (unused for specialist tools currently)
            user_context: Optional user context for RAG tools

        Returns:
            List of specialist tool instances

        Raises:
            ValueError: If specialist profile is unknown
        """
        from taskforce.infrastructure.tools.native.ask_user_tool import AskUserTool

        if specialist == "coding":
            from taskforce.infrastructure.tools.native.file_tools import (
                FileReadTool,
                FileWriteTool,
            )
            from taskforce.infrastructure.tools.native.shell_tool import PowerShellTool

            self.logger.debug(
                "creating_specialist_tools",
                specialist="coding",
                tools=["FileReadTool", "FileWriteTool", "PowerShellTool", "AskUserTool"],
            )

            return [
                FileReadTool(),
                FileWriteTool(),
                PowerShellTool(),
                AskUserTool(),
            ]

        elif specialist == "rag":
            from taskforce.infrastructure.tools.rag.get_document import GetDocumentTool
            from taskforce.infrastructure.tools.rag.list_documents import (
                ListDocumentsTool,
            )
            from taskforce.infrastructure.tools.rag.semantic_search import (
                SemanticSearchTool,
            )

            self.logger.debug(
                "creating_specialist_tools",
                specialist="rag",
                tools=[
                    "SemanticSearchTool",
                    "ListDocumentsTool",
                    "GetDocumentTool",
                    "AskUserTool",
                ],
                has_user_context=user_context is not None,
            )

            return [
                SemanticSearchTool(user_context=user_context),
                ListDocumentsTool(user_context=user_context),
                GetDocumentTool(user_context=user_context),
                AskUserTool(),
            ]

        else:
            raise ValueError(f"Unknown specialist profile: {specialist}")
    
    def _instantiate_tool(
        self, tool_spec: dict, llm_provider: LLMProviderProtocol, user_context: Optional[dict[str, Any]] = None
    ) -> Optional[ToolProtocol]:
        """
        Instantiate a tool from configuration specification.

        Args:
            tool_spec: Tool specification dict with type, module, and params
            llm_provider: LLM provider for tools that need it
            user_context: Optional user context for RAG tools

        Returns:
            Tool instance or None if instantiation fails
        """
        import importlib
        
        tool_type = tool_spec.get("type")
        tool_module = tool_spec.get("module")
        tool_params = tool_spec.get("params", {}).copy()  # Copy to avoid modifying original
        
        if not tool_type or not tool_module:
            self.logger.warning(
                "invalid_tool_spec",
                tool_type=tool_type,
                tool_module=tool_module,
                hint="Tool spec must include 'type' and 'module'",
            )
            return None
        
        try:
            # Import the module
            module = importlib.import_module(tool_module)
            
            # Get the tool class
            tool_class = getattr(module, tool_type)
            
            # Special handling for LLMTool - inject llm_service
            if tool_type == "LLMTool":
                tool_params["llm_service"] = llm_provider
            
            # Special handling for RAG tools - inject user_context
            if tool_type in ["SemanticSearchTool", "ListDocumentsTool", "GetDocumentTool"]:
                if user_context:
                    tool_params["user_context"] = user_context
            
            # Instantiate the tool with params
            tool_instance = tool_class(**tool_params)
            
            self.logger.debug(
                "tool_instantiated",
                tool_type=tool_type,
                tool_name=tool_instance.name,
            )
            
            return tool_instance
            
        except Exception as e:
            self.logger.error(
                "tool_instantiation_failed",
                tool_type=tool_type,
                tool_module=tool_module,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _create_rag_tools(
        self, config: dict, user_context: Optional[dict[str, Any]]
    ) -> list[ToolProtocol]:
        """
        Create RAG tools from configuration (deprecated - tools now in config).

        This method is kept for backward compatibility but RAG tools should
        now be specified in the tools section of the config file.

        Args:
            config: Configuration dictionary
            user_context: User context for security filtering

        Returns:
            Empty list (tools should be in config)
        """
        self.logger.warning(
            "rag_tools_deprecated",
            hint="RAG tools should now be specified in the 'tools' section of config YAML",
        )
        return []

    def _create_todolist_manager(
        self, config: dict, llm_provider: LLMProviderProtocol
    ) -> FileTodoListManager:
        """
        Create TodoList manager with file persistence.

        Args:
            config: Configuration dictionary
            llm_provider: LLM provider for plan generation

        Returns:
            FileTodoListManager instance with persistence support
        """
        work_dir = config.get("persistence", {}).get("work_dir", ".taskforce")
        return FileTodoListManager(work_dir=work_dir, llm_provider=llm_provider)

    def _assemble_system_prompt(self, specialist: str) -> str:
        """
        Assemble system prompt from Kernel + Specialist profile.

        The prompt is composed of:
        1. GENERAL_AUTONOMOUS_KERNEL_PROMPT (shared by all agents)
        2. Specialist-specific prompt (based on profile)

        Args:
            specialist: Specialist profile ("generic", "coding", "rag")

        Returns:
            Assembled system prompt string

        Raises:
            ValueError: If specialist profile is unknown
        """
        from taskforce.core.prompts.autonomous_prompts import (
            CODING_SPECIALIST_PROMPT,
            GENERAL_AUTONOMOUS_KERNEL_PROMPT,
            RAG_SPECIALIST_PROMPT,
        )

        # Start with the autonomous kernel
        system_prompt = GENERAL_AUTONOMOUS_KERNEL_PROMPT

        # Append specialist-specific instructions
        if specialist == "coding":
            system_prompt += "\n\n" + CODING_SPECIALIST_PROMPT
        elif specialist == "rag":
            system_prompt += "\n\n" + RAG_SPECIALIST_PROMPT
        elif specialist == "generic":
            # Generic uses just the kernel (or could use legacy prompt)
            pass
        else:
            raise ValueError(f"Unknown specialist profile: {specialist}")

        self.logger.debug(
            "system_prompt_assembled",
            specialist=specialist,
            prompt_length=len(system_prompt),
        )

        return system_prompt

    def _load_system_prompt(self, agent_type: str) -> str:
        """
        Load system prompt for agent type (legacy method).

        This method is kept for backward compatibility with existing code
        that uses agent_type instead of specialist profiles.

        Args:
            agent_type: Agent type ("generic", "rag", "text2sql", "devops_wiki")

        Returns:
            System prompt string

        Raises:
            ValueError: If agent type is unknown
        """
        if agent_type == "generic":
            # Load generic system prompt
            from taskforce.core.prompts.generic_system_prompt import (
                GENERIC_SYSTEM_PROMPT,
            )

            return GENERIC_SYSTEM_PROMPT

        elif agent_type == "rag":
            # Load RAG system prompt
            from taskforce.core.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT

            return RAG_SYSTEM_PROMPT

        elif agent_type == "text2sql":
            # Load Text2SQL system prompt
            from taskforce.core.prompts.text2sql_system_prompt import TEXT2SQL_SYSTEM_PROMPT

            return TEXT2SQL_SYSTEM_PROMPT

        elif agent_type == "devops_wiki":
            # Load DevOps Wiki system prompt
            from taskforce.core.prompts.wiki_system_prompt import WIKI_SYSTEM_PROMPT
            
            return WIKI_SYSTEM_PROMPT

        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

