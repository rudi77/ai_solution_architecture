# Technical Debt and Known Issues

## Critical Technical Debt

1. **Windows PowerShell Dependency**: Development and deployment instructions assume Windows PowerShell environment, limiting cross-platform adoption
2. **Single-User Model**: No authentication, session isolation, or multi-tenancy support
3. **File-Based Storage**: Pickle files and local directories limit scalability and concurrent access
4. **Synchronous Tool Execution**: Tools execute sequentially, no parallel execution capability
5. **Manual Environment Setup**: Complex setup process requiring multiple manual steps

## Workarounds and Gotchas

- **Prometheus Server**: Embedded on port 8070 in CLI mode, starts automatically with `idp.py`
- **State Persistence**: Uses pickle files which are Python-specific and not human-readable
- **Tool Aliasing**: Tools can be called by multiple names (aliases) - handled via normalization in `tools.py`
- **Loop Guard Protection**: Agent has built-in protection against infinite loops in the ReAct cycle
- **Plan-First Approach**: Agent creates todo lists before execution, departing from pure ReAct pattern