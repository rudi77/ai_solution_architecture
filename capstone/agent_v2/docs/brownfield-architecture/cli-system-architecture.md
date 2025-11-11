# CLI System Architecture

### Command Structure

**Entry Point**: `cli/main.py:cli_main()`

**Main App** (`agent` command):
```
agent
├── run          # Execute missions/tasks
├── chat         # Interactive chat
├── missions     # Mission template management
├── tools        # Tool discovery/management
├── providers    # LLM provider configuration
├── sessions     # Session management
├── config       # Configuration management
├── dev          # Developer tools
└── rag          # RAG-specific commands
```

**Developer App** (`agent-dev` command):
- Separate entry point for debug features
- Same dev tools as main app but direct access

### Plugin Architecture

**Location**: `cli/plugin_manager.py`

**Discovery**:
- Uses Python entry points: `agent_cli_plugins` group
- Plugins register via `pyproject.toml`:
  ```toml
  [project.entry-points."agent_cli_plugins"]
  my-plugin = "package.plugins:MyPluginClass"
  ```

**Plugin Interface** (from CLI README):
```python
class CLIPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def command_group(self) -> typer.Typer: pass

    def setup(self, main_app: typer.Typer) -> None: pass
```

**Security**: TODO - Plugin validation not yet implemented (noted in PRD NFR5)

### Output Formatting

**Location**: `cli/output_formatter.py`

**Formats**:
- `table` (default): Rich tables with colored headers
- `json`: Machine-readable JSON output
- `yaml`: Human-readable YAML
- `text`: Plain text (for piping)

**Usage**: All list commands support `--output <format>` flag

### Configuration Management

**Location**: `cli/config/settings.py`

**Features**:
- Pydantic-based settings with validation
- Environment variable overrides (prefix: `AGENT_`)
- File-based persistence (default: `~/.agent/config.yaml`)
- Hierarchical settings (user > system > defaults)

**Key Settings** (from CLI README):
- `default_provider`: LLM provider ID
- `default_output_format`: CLI output format
- `tool_discovery_paths`: Paths to search for tools
- `session_cleanup_days`: Auto-cleanup threshold
- `debug_mode`: Enable debug logging

### Command Implementation Status

**Fully Implemented** (based on file analysis):
- ✅ **run**: Execute missions and tasks
- ✅ **chat**: Interactive agent chat (21KB file - substantial implementation)
- ✅ **missions**: Mission template management
- ✅ **tools**: Tool discovery and management
- ✅ **providers**: LLM provider configuration
- ✅ **sessions**: Session management
- ✅ **config**: Configuration management
- ✅ **dev**: Developer tools
- ✅ **rag**: RAG commands (14KB file - recent addition)

**Notes**:
- CLI PRD describes 35+ individual commands across these groups
- Each command file is 6-21KB suggesting substantial (not stub) implementations
- CLI README shows comprehensive examples for all command groups

---
