# Agent V2 Rich CLI

A modern, extensible command-line interface for the Agent V2 platform, built with Typer and Rich for an exceptional developer experience.

## Features

### 🚀 Modern CLI Framework
- Built on Typer with Rich terminal formatting
- Auto-completion for commands, options, and dynamic values
- Beautiful colored output, tables, and progress bars
- Consistent command structure and help system

### 🔧 Extensible Plugin Architecture
- Plugin discovery via Python entry points
- Easy third-party command group integration
- Secure plugin validation and loading
- Example plugins included

### 📊 Rich Interactive Experience
- Multiple output formats: table, JSON, YAML, text
- Interactive parameter collection with validation
- Progress visualization for long-running operations
- Comprehensive error handling with recovery suggestions

### ⚙️ Configuration Management
- Hierarchical configuration with environment variable support
- File-based persistence with YAML format
- Import/export configuration capabilities
- Per-setting validation and type conversion

### 🛠️ Developer Tools
- Interactive shell mode with session persistence
- Debug mode execution with detailed output
- Performance profiling and benchmarking
- Comprehensive logging and monitoring

## Installation

1. Install the agent platform:
```bash
cd capstone/agent_v2
pip install -e .
```

2. Verify installation:
```bash
agent --version
agent --help
```

## Quick Start

### Execute a Mission
```bash
# Run a mission template interactively
agent run mission data-analysis --provider openai

# Batch mode execution
agent run mission code-review --batch --output json

# Execute a one-off task
agent run task "Analyze the logs for errors" --context ./logs
```

### Manage Mission Templates
```bash
# List available missions
agent missions list

# Show mission details
agent missions show data-analysis

# Create new mission
agent missions create my-mission --category automation

# Validate mission template
agent missions validate ./mission.yaml
```

### Tool Management
```bash
# List available tools
agent tools list

# Install a tool
agent tools install web_tool

# Test tool functionality
agent tools test data_analyzer --verbose

# Discover local tools
agent tools discover
```

### Provider Configuration
```bash
# List configured providers
agent providers list

# Add new provider
agent providers add anthropic --name claude-work

# Test provider connection
agent providers test openai-main

# Set default provider
agent providers set-default anthropic-claude
```

### Session Management
```bash
# List recent sessions
agent sessions list --limit 10

# Show session details
agent sessions show sess-abc123 --logs

# Resume interrupted session
agent sessions resume sess-def456

# Export session data
agent sessions export sess-ghi789 --output session.json
```

### Configuration
```bash
# Show current configuration
agent config show

# Update setting
agent config set default_provider anthropic

# Export configuration
agent config export backup.yaml

# Reset to defaults
agent config reset
```

### Developer Tools
```bash
# Interactive shell
agent dev shell

# View logs
agent dev logs --follow

# Debug command execution
agent dev debug "missions list" --verbose

# Performance profiling
agent dev profile "run data-analysis"
```

## Command Structure

```
agent                                    # Main CLI entry point
├── run                                  # Execute missions and tasks
│   ├── mission <template> [options]     # Execute mission template
│   └── task <description> [options]     # Execute ad-hoc task
├── missions                             # Mission template management
│   ├── list [--category]               # List templates
│   ├── show <template>                  # Show details
│   ├── create <name>                    # Create template
│   ├── edit <template>                  # Edit template
│   ├── validate <file>                  # Validate syntax
│   └── import <file>                    # Import template
├── tools                                # Tool management
│   ├── list [--category]               # List tools
│   ├── install <tool>                   # Install tool
│   ├── configure <tool>                 # Configure tool
│   ├── test <tool>                      # Test tool
│   ├── discover                         # Discover tools
│   └── registry <action>                # Manage registry
├── providers                            # LLM provider management
│   ├── list                            # List providers
│   ├── add <type>                      # Add provider
│   ├── configure <provider>            # Configure provider
│   ├── test <provider>                 # Test connection
│   ├── set-default <provider>          # Set default
│   └── models <provider>               # List models
├── sessions                            # Session management
│   ├── list [--status]                # List sessions
│   ├── show <session>                  # Show details
│   ├── resume <session>                # Resume session
│   ├── export <session>                # Export data
│   └── cleanup [--older-than]          # Cleanup old sessions
├── config                              # Configuration management
│   ├── show                           # Show config
│   ├── set <key> <value>              # Set value
│   ├── reset                          # Reset defaults
│   ├── export <file>                  # Export config
│   ├── import <file>                  # Import config
│   └── validate                       # Validate config
└── dev                                 # Developer tools
    ├── shell                          # Interactive shell
    ├── logs [--follow]                # View logs
    ├── debug <command>                # Debug mode
    ├── version [--detailed]           # Version info
    ├── profile <command>              # Performance profiling
    ├── test-integration               # Integration tests
    └── benchmark                      # Benchmark commands
```

## Plugin Development

### Creating a Plugin

1. Create a plugin class inheriting from `CLIPlugin`:

```python
from capstone.agent_v2.cli.plugin_manager import CLIPlugin
import typer

class MyPlugin(CLIPlugin):
    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def command_group(self) -> typer.Typer:
        app = typer.Typer(name="my", help="My custom commands")

        @app.command()
        def hello():
            """Say hello."""
            print("Hello from my plugin!")

        return app

    def setup(self, main_app: typer.Typer) -> None:
        """Setup plugin with main app."""
        pass
```

2. Register via entry points in `pyproject.toml`:

```toml
[project.entry-points."agent_cli_plugins"]
my-plugin = "my_package.plugins:MyPlugin"
```

3. Install and use:

```bash
pip install my-plugin-package
agent my hello
```

### Example Plugins

- **Database Plugin**: Database management commands (migrate, backup, query)
- **Monitoring Plugin**: System monitoring and alerting
- **Deployment Plugin**: Application deployment automation

## Configuration

### Configuration File

Default location: `~/.agent/config.yaml`

```yaml
# Provider settings
default_provider: openai
default_output_format: table

# UI preferences
auto_confirm: false
show_progress: true
color_output: true

# Tool discovery
tool_discovery_paths:
  - ./tools
  - ~/.agent/tools
auto_install_tools: false

# Mission templates
mission_template_paths:
  - ./missions
  - ~/.agent/missions

# Session management
session_cleanup_days: 30
session_storage_path: ~/.agent/sessions

# Debug settings
debug_mode: false
log_level: INFO
log_file: ~/.agent/agent.log
```

### Environment Variables

All settings can be overridden with environment variables using the `AGENT_` prefix:

```bash
export AGENT_DEFAULT_PROVIDER=anthropic
export AGENT_DEBUG_MODE=true
export AGENT_LOG_LEVEL=DEBUG
```

## Output Formats

All list commands support multiple output formats:

### Table (default)
```bash
agent missions list
```

### JSON
```bash
agent missions list --output json
```

### YAML
```bash
agent missions list --output yaml
```

### Text
```bash
agent missions list --output text
```

## Auto-completion

Enable shell auto-completion:

### Bash
```bash
eval "$(_AGENT_COMPLETE=bash_source agent)"
```

### Zsh
```bash
eval "$(_AGENT_COMPLETE=zsh_source agent)"
```

### Fish
```bash
eval (env _AGENT_COMPLETE=fish_source agent)
```

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest cli/tests/

# Run with coverage
pytest cli/tests/ --cov=cli/
```

### Contributing

1. Follow the existing command structure and patterns
2. Add comprehensive tests for new features
3. Update documentation and help text
4. Ensure cross-platform compatibility
5. Test plugin architecture if adding new extension points

## Architecture

### Core Components

- **Main CLI**: Entry point and command group registration
- **Plugin Manager**: Plugin discovery and loading system
- **Output Formatter**: Multi-format output rendering
- **Configuration**: Settings management with validation
- **Commands**: Individual command group implementations

### Extension Points

- **CLI Plugins**: Add new command groups via entry points
- **Output Formatters**: Custom output format implementations
- **Configuration Sources**: Additional configuration providers
- **Auto-completion**: Custom completion sources

## Performance

### Startup Time
- Target: <200ms for simple commands
- Plugin lazy loading for optimal performance
- Minimal dependency imports in critical paths

### Memory Usage
- Efficient Rich rendering with streaming
- Plugin isolation to prevent memory leaks
- Configuration caching for repeated operations

### Scalability
- Command structure supports unlimited plugin extensions
- Configuration system handles large value sets
- Session management scales to thousands of concurrent sessions

## Security

### Plugin Security
- Plugin validation before loading
- Isolated execution environments
- Digital signature verification (planned)

### Configuration Security
- Sensitive value masking in output
- Secure storage for API keys and credentials
- Permission-based configuration access

### Network Security
- TLS verification for all external connections
- Configurable proxy support
- Rate limiting for API calls

## Troubleshooting

### Common Issues

**CLI not found after installation**
```bash
# Ensure pip installed to correct location
pip show hybrid-agent
# Add to PATH if needed
export PATH="$PATH:~/.local/bin"
```

**Plugin loading errors**
```bash
# Check plugin registration
agent dev version --detailed
# Validate plugin entry points
python -c "import pkg_resources; print(list(pkg_resources.iter_entry_points('agent_cli_plugins')))"
```

**Configuration issues**
```bash
# Validate configuration
agent config validate
# Reset to defaults
agent config reset --confirm
```

**Performance issues**
```bash
# Profile command execution
agent dev profile "missions list"
# Check startup time
time agent --help
```

### Debug Mode

Enable debug output for troubleshooting:

```bash
agent --verbose <command>
agent dev debug "<command>"
```

### Logging

Configure logging for detailed diagnostics:

```bash
agent config set log_level DEBUG
agent config set log_file ~/.agent/debug.log
agent dev logs --follow
```