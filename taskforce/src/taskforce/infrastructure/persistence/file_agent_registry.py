"""
File-Based Agent Registry
==========================

Provides CRUD operations for custom agent definitions stored as YAML files.

Responsibilities:
- Persist custom agents to `configs/custom/{agent_id}.yaml`
- List all agents (custom + profile configs)
- Atomic writes for Windows compatibility
- Graceful handling of corrupt YAML files

Story: 8.1 - Custom Agent Registry (CRUD + YAML Persistence)
"""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from taskforce.api.schemas.agent_schemas import (
    CustomAgentCreate,
    CustomAgentResponse,
    CustomAgentUpdate,
    ProfileAgentResponse,
)

logger = structlog.get_logger()


class FileAgentRegistry:
    """
    File-based agent registry with YAML persistence.

    Manages custom agent definitions and scans profile configurations.

    Directory structure:
        configs/custom/{agent_id}.yaml - Custom agents
        configs/*.yaml - Profile agents (excluding llm_config.yaml)

    Thread Safety:
        Not thread-safe. Use appropriate locking if concurrent access needed.

    Example:
        >>> registry = FileAgentRegistry()
        >>> agent = CustomAgentCreate(
        ...     agent_id="test-agent",
        ...     name="Test Agent",
        ...     description="Test",
        ...     system_prompt="You are a test agent",
        ...     tool_allowlist=["python"]
        ... )
        >>> created = registry.create_agent(agent)
        >>> assert created.agent_id == "test-agent"
    """

    def __init__(self, configs_dir: str = "configs"):
        """
        Initialize the agent registry.

        Args:
            configs_dir: Root directory for configuration files.
                        Defaults to "configs" relative to current directory.
        """
        self.configs_dir = Path(configs_dir)
        self.custom_dir = self.configs_dir / "custom"
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="file_agent_registry")

    def _get_agent_path(self, agent_id: str) -> Path:
        """Get the file path for an agent definition."""
        return self.custom_dir / f"{agent_id}.yaml"

    def _atomic_write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """
        Write YAML atomically using temp file + rename.

        Windows-safe implementation:
        1. Write to temp file in same directory
        2. If target exists, delete it first (Windows requirement)
        3. Rename temp to target

        Args:
            path: Target file path
            data: Dictionary to serialize as YAML

        Raises:
            OSError: If file operations fail
        """
        # Write to temp file in same directory (ensures same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp", prefix=".agent_"
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            # Windows: must delete target before rename
            if path.exists():
                path.unlink()

            # Atomic rename
            Path(temp_path).rename(path)

            self.logger.debug(
                "agent.yaml.written", agent_file=str(path), atomic=True
            )

        except Exception:
            # Clean up temp file on error
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    def _load_custom_agent(self, agent_id: str) -> Optional[CustomAgentResponse]:
        """
        Load a custom agent from YAML file.

        Args:
            agent_id: Agent identifier

        Returns:
            CustomAgentResponse if found and valid, None otherwise
        """
        path = self._get_agent_path(agent_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validate and construct response
            return CustomAgentResponse(
                agent_id=data["agent_id"],
                name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
                tool_allowlist=data.get("tool_allowlist", []),
                mcp_servers=data.get("mcp_servers", []),
                mcp_tool_allowlist=data.get("mcp_tool_allowlist", []),
                created_at=data["created_at"],
                updated_at=data["updated_at"],
            )

        except Exception as e:
            self.logger.warning(
                "agent.yaml.corrupt",
                agent_id=agent_id,
                path=str(path),
                error=str(e),
            )
            return None

    def _load_profile_agent(self, profile_path: Path) -> Optional[ProfileAgentResponse]:
        """
        Load a profile agent from YAML config file.

        Args:
            profile_path: Path to profile YAML file

        Returns:
            ProfileAgentResponse if valid, None if corrupt
        """
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Extract profile name from filename (without .yaml)
            profile_name = profile_path.stem

            return ProfileAgentResponse(
                profile=profile_name,
                specialist=data.get("specialist"),
                tools=data.get("tools", []),
                mcp_servers=data.get("mcp_servers", []),
                llm=data.get("llm", {}),
                persistence=data.get("persistence", {}),
            )

        except Exception as e:
            self.logger.warning(
                "profile.yaml.corrupt",
                profile=profile_path.name,
                path=str(profile_path),
                error=str(e),
            )
            return None

    def create_agent(self, agent_def: CustomAgentCreate) -> CustomAgentResponse:
        """
        Create a new custom agent.

        Args:
            agent_def: Agent definition to create

        Returns:
            CustomAgentResponse with timestamps

        Raises:
            FileExistsError: If agent_id already exists
        """
        path = self._get_agent_path(agent_def.agent_id)

        if path.exists():
            raise FileExistsError(f"Agent '{agent_def.agent_id}' already exists")

        # Add timestamps
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "agent_id": agent_def.agent_id,
            "name": agent_def.name,
            "description": agent_def.description,
            "system_prompt": agent_def.system_prompt,
            "tool_allowlist": agent_def.tool_allowlist,
            "mcp_servers": agent_def.mcp_servers,
            "mcp_tool_allowlist": agent_def.mcp_tool_allowlist,
            "created_at": now,
            "updated_at": now,
        }

        self._atomic_write_yaml(path, data)

        self.logger.info(
            "agent.created", agent_id=agent_def.agent_id, path=str(path)
        )

        return CustomAgentResponse(**data)

    def get_agent(
        self, agent_id: str
    ) -> Optional[CustomAgentResponse | ProfileAgentResponse]:
        """
        Get an agent by ID.

        Searches custom agents first, then profile agents.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent definition if found, None otherwise
        """
        # Try custom agents first
        custom = self._load_custom_agent(agent_id)
        if custom:
            return custom

        # Try profile agents (agent_id matches profile name)
        profile_path = self.configs_dir / f"{agent_id}.yaml"
        if profile_path.exists() and agent_id != "llm_config":
            return self._load_profile_agent(profile_path)

        return None

    def list_agents(
        self,
    ) -> list[CustomAgentResponse | ProfileAgentResponse]:
        """
        List all agents (custom + profile).

        Scans:
        - configs/custom/*.yaml (custom agents)
        - configs/*.yaml (profile agents, excluding llm_config.yaml)

        Corrupt YAML files are skipped with warning logged.

        Returns:
            List of all valid agent definitions
        """
        agents: list[CustomAgentResponse | ProfileAgentResponse] = []

        # Load custom agents
        if self.custom_dir.exists():
            for yaml_file in self.custom_dir.glob("*.yaml"):
                agent_id = yaml_file.stem
                agent = self._load_custom_agent(agent_id)
                if agent:
                    agents.append(agent)

        # Load profile agents
        if self.configs_dir.exists():
            for yaml_file in self.configs_dir.glob("*.yaml"):
                # Skip llm_config.yaml and custom directory
                if yaml_file.name == "llm_config.yaml":
                    continue
                if yaml_file.parent.name == "custom":
                    continue

                profile = self._load_profile_agent(yaml_file)
                if profile:
                    agents.append(profile)

        self.logger.debug("agents.listed", count=len(agents))
        return agents

    def update_agent(
        self, agent_id: str, agent_def: CustomAgentUpdate
    ) -> CustomAgentResponse:
        """
        Update an existing custom agent.

        Args:
            agent_id: Agent identifier to update
            agent_def: New agent definition

        Returns:
            Updated CustomAgentResponse

        Raises:
            FileNotFoundError: If agent doesn't exist
        """
        path = self._get_agent_path(agent_id)

        if not path.exists():
            raise FileNotFoundError(f"Agent '{agent_id}' not found")

        # Load existing to preserve created_at
        existing = self._load_custom_agent(agent_id)
        if not existing:
            raise FileNotFoundError(f"Agent '{agent_id}' is corrupt")

        # Update with new data
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "agent_id": agent_id,
            "name": agent_def.name,
            "description": agent_def.description,
            "system_prompt": agent_def.system_prompt,
            "tool_allowlist": agent_def.tool_allowlist,
            "mcp_servers": agent_def.mcp_servers,
            "mcp_tool_allowlist": agent_def.mcp_tool_allowlist,
            "created_at": existing.created_at,  # Preserve
            "updated_at": now,
        }

        self._atomic_write_yaml(path, data)

        self.logger.info(
            "agent.updated", agent_id=agent_id, path=str(path)
        )

        return CustomAgentResponse(**data)

    def delete_agent(self, agent_id: str) -> None:
        """
        Delete a custom agent.

        Args:
            agent_id: Agent identifier to delete

        Raises:
            FileNotFoundError: If agent doesn't exist
        """
        path = self._get_agent_path(agent_id)

        if not path.exists():
            raise FileNotFoundError(f"Agent '{agent_id}' not found")

        path.unlink()

        self.logger.info(
            "agent.deleted", agent_id=agent_id, path=str(path)
        )

