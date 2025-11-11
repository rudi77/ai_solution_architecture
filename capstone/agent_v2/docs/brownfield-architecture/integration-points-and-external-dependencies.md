# Integration Points and External Dependencies

### LLM Providers

**Integration**: LiteLLM library (version 1.7.7.0)

**Supported Providers**:
- OpenAI (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- Anthropic (claude models)
- Others via LiteLLM's unified interface

**Configuration**:
- Provider credentials via environment variables (e.g., `OPENAI_API_KEY`)
- Model selection per agent instance
- Default provider managed via CLI `providers` commands

**Model Usage**:
- Agent reasoning: User-specified model (e.g., "gpt-4")
- Message compression: Hardcoded "gpt-4.1" in `MessageHistory.compress_history_async()`
- Tool generation (LLMTool): Inherits from agent config or overridable

### Azure AI Search

**Integration**: Azure Search Documents SDK (11.4.0+)

**Purpose**: RAG knowledge retrieval backend

**Connection**:
- Endpoint, key, and index name via environment variables
- Shared client in `tools/azure_search_base.py`
- Used by SemanticSearchTool, ListDocumentsTool, GetDocumentTool

**Index Schema** (inferred from content blocks):
- Text chunks with embeddings
- Image metadata with captions and URLs
- Document metadata (title, page numbers, chunk numbers)
- Security metadata for filtering

### External Services

| Service      | Purpose                      | Integration Type | Key Files/Config                     |
| ------------ | ---------------------------- | ---------------- | ------------------------------------ |
| OpenAI       | LLM reasoning & generation   | REST API         | OPENAI_API_KEY env var               |
| Azure Search | RAG semantic search          | SDK              | AZURE_SEARCH_* env vars              |
| GitHub       | Git operations (optional)    | REST API         | GITHUB_TOKEN env var                 |
| Web          | Search and fetch (via tools) | HTTP             | WebSearchTool, WebFetchTool          |

### File System Dependencies

**State Storage**:
- Default: `./agent_states/{session_id}.pkl`
- Configurable via StateManager constructor

**TodoList Storage**:
- Default: `{work_dir}/todolists/{todolist_id}.json`
- Work directory specified per agent/session

**CLI Configuration**:
- Default: `~/.agent/config.yaml`
- Environment override: `AGENT_CONFIG_PATH`

**Session Logs**:
- Mentioned in CLI commands but location TBD (check dev/logs implementation)

---
