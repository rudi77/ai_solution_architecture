# Tool Framework Architecture

### Base Tool Interface

**Location**: `tool.py:10-168`

**Abstract Methods**:
- `name` (property): Tool identifier
- `description` (property): Natural language description
- `execute(**kwargs)`: Async method returning `Dict[str, Any]`

**Provided Methods**:
- `parameters_schema`: Auto-generated from `execute()` signature or manual override
- `function_tool_schema`: OpenAI function calling format
- `execute_safe()`: Robust wrapper with validation, retry, timeout, error handling
- `validate_params()`: Check required parameters before execution

**Execution Safety**:
- Max 3 retry attempts with exponential backoff (2^attempt seconds)
- 60-second timeout per execution
- Validation of parameters against signature
- Validation of return type (must be dict with "success" field)
- Comprehensive error capture with traceback

### Built-in Tools

#### PythonTool (`tools/code_tool.py`)

**CRITICAL DESIGN CONSTRAINT**: Each execution runs in an **isolated namespace**. Variables from previous steps DO NOT persist.

**Available Imports** (pre-imported):
- Standard: `os, sys, json, re, pathlib, shutil, subprocess, datetime, time, random, base64, hashlib, tempfile, csv`
- Optional: `pandas as pd, matplotlib.pyplot as plt` (if installed)
- Types: `Dict, List, Any, Optional`

**Context Handling**:
- Pass data via `context` dict parameter
- Context keys exposed as top-level variables in execution namespace
- Code must assign final output to `result` variable

**Working Directory**:
- Supports `cwd` parameter for path-relative operations
- Windows path handling (backslash conversion, quote stripping, expandvars)
- Validation: Checks if cwd exists and is directory before execution

**Error Recovery** (from CLAUDE.md):
> Agent handles namespace isolation via:
> 1. Pass data through context parameter (simple data)
> 2. Re-read from source files (CSV, JSON, etc.)
> 3. Error recovery with hints on retry attempts

#### FileReadTool & FileWriteTool (`tools/file_tool.py`)

- Basic file I/O operations
- **Note**: Implementation details not fully reviewed, check source for specifics

#### PowerShellTool (`tools/shell_tool.py`)

- **Windows-focused**: Executes PowerShell commands
- Used for Windows system operations, git commands, etc.
- **Platform dependency**: Will NOT work on Linux/Mac without modification

#### WebSearchTool & WebFetchTool (`tools/web_tool.py`)

- Web search and content fetching
- Details in source file

#### GitTool & GitHubTool (`tools/git_tool.py`)

- Git operations via PowerShell
- GitHub API operations (requires `GITHUB_TOKEN` environment variable)
- Windows path handling for `repo_path` parameters

#### LLMTool (`tools/llm_tool.py`)

**Purpose**: Natural language text generation (distinct from agent's own LLM calls)

**Use Cases**:
- RAG synthesis: Combining search results into cohesive responses
- Content generation within agent workflows
- Summary generation

**Parameters**:
- `prompt`: The generation prompt
- `context`: Additional context dict (optional)
- LLM model/temperature inherited from agent config or specified

#### RAG Tools (`tools/rag_*.py`)

**Base**: `azure_search_base.py` - Shared Azure AI Search client configuration

**SemanticSearchTool** (`rag_semantic_search_tool.py`):
- Input: `{"query": str, "top_k": int}`
- Output: List of content blocks (text + images) with relevance scores
- Returns: `block_id, block_type, content_text, image_url, image_caption, document_id, document_title, page_number, score`

**ListDocumentsTool** (`rag_list_documents_tool.py`):
- Input: `{"filters": dict, "limit": int}`
- Output: List of document metadata
- Filters: document_type, date_range, author, keywords

**GetDocumentTool** (`rag_get_document_tool.py`):
- Input: `{"document_id": str}`
- Output: Complete document metadata and summary

### Tool Registration

**Generic Agent**:
```python
tools = [
    PythonTool(),
    FileReadTool(),
    FileWriteTool(),
    PowerShellTool(),
    WebSearchTool(),
    WebFetchTool(),
    GitTool(),
    GitHubTool(),
    LLMTool()
]
```

**RAG Agent**:
```python
tools = [
    SemanticSearchTool(),
    ListDocumentsTool(),
    GetDocumentTool(),
    LLMTool(),
    PythonTool()  # For programmatic synthesis (optional)
]
```

---
