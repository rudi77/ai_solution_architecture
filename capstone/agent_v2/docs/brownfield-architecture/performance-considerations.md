# Performance Considerations

### Startup Performance

**Target**: <200ms for simple commands (NFR1)

**Current Status**: Not measured

**Potential Issues**:
- Rich library import overhead
- Plugin discovery on startup
- Configuration file loading
- LiteLLM initialization

**Optimization Opportunities**:
- Lazy load plugins (only when needed)
- Cache configuration in memory
- Defer Rich imports to command execution
- Profile with `agent dev profile` command

### Memory Usage

**State Files**: Pickle format with versioning - size depends on message history length

**Considerations**:
- Message history compression after 40 message pairs
- TodoList JSON persistence (lightweight)
- Session cleanup after 7 days (configurable)

**Potential Issues**:
- Large state files if compression fails
- Memory leaks in long-running sessions (not verified)

### LLM Call Efficiency

**Current Pattern**:
- Plan generation: 1 LLM call per new mission
- Execution loop: 1 LLM call per TodoItem (thought + action decision)
- Message compression: 1 LLM call when threshold exceeded
- RAG synthesis: 1 additional LLM call (if using LLMTool approach)

**Optimization Opportunities**:
- Batch multiple TodoItem decisions (risky - less precise)
- Use cheaper models for compression
- Cache common plans (mission template system)

---
