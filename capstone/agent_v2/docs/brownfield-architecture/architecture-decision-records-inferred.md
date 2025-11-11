# Architecture Decision Records (Inferred)

### Why LiteLLM?

**Decision**: Use LiteLLM for LLM provider abstraction

**Rationale**:
- Unified interface across OpenAI, Anthropic, and other providers
- Easy provider switching without code changes
- Built-in retry and fallback logic
- Active maintenance and broad provider support

**Tradeoffs**:
- Additional dependency layer
- Provider-specific features may not be exposed
- Version 1.7.7.0 used (not latest) - may be stability vs features decision

### Why Typer + Rich for CLI?

**Decision**: Typer framework with Rich terminal formatting

**Rationale**:
- Modern Python CLI framework with type hints
- Auto-generated help and validation
- Rich provides beautiful terminal output (tables, progress bars, colors)
- Strong ecosystem and documentation

**Tradeoffs**:
- Larger dependency footprint than argparse
- Windows Unicode issues required workarounds
- Startup time potentially slower (NFR1 concern)

### Why TodoList Planning?

**Decision**: LLM-generated TodoList with structured tasks instead of free-form execution

**Rationale**:
- Provides structure and transparency (user can see plan before execution)
- Enables dependency tracking and parallel execution
- Facilitates state recovery (resume from interrupted sessions)
- Acceptance criteria define "done" independent of implementation

**Tradeoffs**:
- Additional LLM call for planning (cost + latency)
- LLM may generate suboptimal plans requiring replanning
- JSON schema enforcement can cause parsing errors

### Why Isolated PythonTool Namespace?

**Decision**: Each PythonTool execution uses fresh namespace

**Rationale**:
- Security: Prevents unintended side effects between executions
- Isolation: Each tool call is independent and testable
- Clean state: No accumulated globals or stale state

**Tradeoffs**:
- Cannot persist variables between executions
- Increases complexity of multi-step data processing
- Agent must re-read data or use context parameter

### Why Async State Persistence?

**Decision**: Async file I/O with locks for state management

**Rationale**:
- Non-blocking I/O for better performance
- Locks prevent race conditions in concurrent access
- Versioning enables optimistic concurrency control

**Tradeoffs**:
- More complex than synchronous file I/O
- Pickle format not human-readable (YAML would be better for debugging)

---
