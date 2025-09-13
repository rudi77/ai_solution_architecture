# Integration Points and External Dependencies

## External Services

| Service  | Purpose  | Integration Type | Key Files                      |
| -------- | -------- | ---------------- | ------------------------------ |
| OpenAI API | Primary LLM | REST API + Function Calling | `prototype/llm_provider.py` |
| Anthropic API | Secondary LLM | REST API | `prototype/llm_provider.py` |
| GitHub API | Repository Ops | REST API via PyGithub | `prototype/tools_builtin.py` |
| Kubernetes API | Cluster Ops | Python client | `prototype/tools_builtin.py` |
| Git CLI | Local Repo Ops | Subprocess calls | `prototype/tools_builtin.py` |

## Internal Integration Points

- **Frontend ↔ Backend**: HTTP REST + Server-Sent Events (SSE) for real-time streaming
- **Agent ↔ Tools**: Normalized name lookup with async execution and timeout protection
- **Agent ↔ LLM**: Function calling with tool schema export to OpenAI format
- **State ↔ Storage**: Atomic pickle serialization with error recovery