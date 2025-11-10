# 4.2 Epic 1: Multimodal RAG Knowledge Retrieval for Agent Framework

**Epic Goal:**
Extend the existing agent_v2 ReAct framework with Azure AI Search-powered multimodal knowledge retrieval capabilities, enabling autonomous search across text and images with intelligent synthesis of markdown responses including embedded visuals and source citations.

**Integration Requirements:**
- Maintain full backward compatibility with existing Agent.execute() interface
- Preserve all existing tools (WebSearch, FileTool, PythonTool, etc.) functionality
- Use existing StateManager, TodoListManager, and MessageHistory without modifications
- Follow existing async/await patterns and AgentEvent streaming architecture
- Integrate Azure Search Python SDK alongside existing tool patterns

---

### Story 1.1: Azure AI Search SDK Integration and Base Tool Infrastructure

**As a** developer maintaining the agent framework,
**I want** to establish the Azure AI Search SDK connection infrastructure,
**so that** all RAG tools can reliably connect to Azure and execute queries with proper authentication and error handling.

#### Acceptance Criteria

**AC1.1.1:** A new module `tools/azure_search_base.py` exists containing an `AzureSearchBase` class that:
- Loads environment variables (AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, index names)
- Validates required variables and raises `ValueError` with clear instructions if missing
- Provides `get_search_client(index_name: str) -> AsyncSearchClient` method
- Implements proper async context manager pattern

**AC1.1.2:** The `AzureSearchBase` class includes a method `build_security_filter(user_context: Dict) -> str` that:
- Accepts user_context with user_id, department, org_id
- Returns OData filter string: `access_control_list/any(acl: acl eq 'user_id' or acl eq 'department')`
- Handles missing user_context gracefully (returns empty filter for testing)

**AC1.1.3:** requirements.txt includes:
```
azure-search-documents>=11.4.0
azure-core>=1.29.0
```

**AC1.1.4:** Unit tests exist for `AzureSearchBase`:
- Test environment variable validation (missing ENDPOINT raises ValueError)
- Test security filter generation with various user_context inputs
- Test SearchClient creation returns AsyncSearchClient instance

**AC1.1.5:** Integration test connects to real Azure AI Search endpoint using test credentials and successfully executes a basic search query

#### Integration Verification

- **IV1.1.1:** All existing agent tests pass without modification (no regression)
- **IV1.1.2:** Existing tools (WebSearchTool, FileReadTool) continue to function normally
- **IV1.1.3:** Agent.create_agent() works without RAG tools (backward compatibility preserved)

---

### Story 1.2: Semantic Search Tool for Content Blocks

**As a** RAG-enabled agent,
**I want** to search across multimodal content blocks (text and images) semantically,
**so that** I can retrieve relevant information including diagrams and visualizations for user queries.

#### Acceptance Criteria

**AC1.2.1:** A new tool `SemanticSearchTool` exists in `tools/rag_semantic_search_tool.py` that:
- Inherits from `Tool` base class (tool.py)
- Implements `name = "rag_semantic_search"`
- Provides `description` explaining multimodal search capability
- Defines `parameters_schema` with: query (str, required), top_k (int, default=10), filters (dict, optional)

**AC1.2.2:** The `execute(**kwargs)` async method:
- Accepts: query, top_k, filters, user_context
- Uses `AsyncSearchClient` to search the content-blocks index
- Applies security filter from user_context via `build_security_filter()`
- Returns structured result:
```python
{
  "success": True,
  "results": [
    {
      "block_id": "...",
      "block_type": "text|image",
      "content": "..." (if text),
      "image_url": "..." (if image),
      "image_caption": "..." (if image),
      "doc_id": "...",
      "filename": "...",
      "page_number": 5,
      "score": 0.85
    }
  ],
  "result_count": 10
}
```

**AC1.2.3:** Error handling:
- Azure SDK exceptions caught and returned as `{"success": False, "error": "...", "type": "AzureSearchError", "hints": [...]}`
- Network timeouts (30s) handled gracefully
- Empty results return `{"success": True, "results": [], "result_count": 0}`

**AC1.2.4:** Structured logging with structlog:
- Logs: `azure_operation="search"`, `search_query`, `result_count`, `index_name="content-blocks"`, `search_latency_ms`

**AC1.2.5:** Unit tests with mocked AsyncSearchClient verify:
- Successful search returns properly formatted results
- Empty results handled correctly
- Azure exceptions converted to agent error format
- Security filter correctly applied

**AC1.2.6:** Integration test against real Azure index retrieves actual content blocks

#### Integration Verification

- **IV1.2.1:** Tool can be registered in Agent.create_agent() tools list without errors
- **IV1.2.2:** Agent can execute a TodoItem that calls rag_semantic_search and receives results
- **IV1.2.3:** Existing agent performance unaffected (non-RAG missions execute in same time)

---

### Story 1.3: Document Metadata Tools (List and Get)

**As a** RAG-enabled agent,
**I want** to list available documents and retrieve document summaries,
**so that** I can answer queries about document availability and provide pre-computed summaries without full-text search.

#### Acceptance Criteria

**AC1.3.1:** A new tool `ListDocumentsTool` exists in `tools/rag_list_documents_tool.py` that:
- Inherits from `Tool` base class
- Implements `name = "rag_list_documents"`
- Parameters: filters (dict, optional), sort_by (str, default="upload_date"), limit (int, default=20), user_context
- Searches the `documents-metadata` index
- Returns: `{"success": True, "documents": [{"doc_id", "filename", "title", "document_type", "upload_date", "summary_brief"}], "count": N}`

**AC1.3.2:** A new tool `GetDocumentTool` exists in `tools/rag_get_document_tool.py` that:
- Implements `name = "rag_get_document"`
- Parameters: doc_id (str, required), user_context
- Uses AsyncSearchClient to retrieve single document by doc_id
- Returns: `{"success": True, "document": {"doc_id", "filename", "title", "summary_standard", "page_count", ...}}`

**AC1.3.3:** Both tools apply security filter from user_context

**AC1.3.4:** Error handling for document not found, access denied, Azure errors

**AC1.3.5:** Unit tests for both tools with mocked Azure responses

**AC1.3.6:** Integration tests retrieve actual documents from Azure index

#### Integration Verification

- **IV1.3.1:** Both tools register successfully in Agent.create_agent()
- **IV1.3.2:** Agent can execute TodoItems calling these tools
- **IV1.3.3:** Tools work alongside rag_semantic_search without conflicts

---

### Story 1.3.1: Generic LLM Tool for Response Generation

**As a** agent framework developer,
**I want** a generic LLM tool that enables any agent to generate natural language text,
**so that** agents can formulate responses to users, create summaries, and perform text generation tasks as explicit tool actions within their workflow.

**Business Context:**
After retrieving data via tools (e.g., rag_list_documents), agents need a way to formulate natural language responses to users. Currently, agents have no tool-based mechanism for text generation, leading to incomplete interactions where tool results are returned but no human-readable response is provided.

#### Acceptance Criteria

**AC1.3.1.1:** A new generic tool `LLMTool` exists in `tools/llm_tool.py` that:
- Inherits from `Tool` base class
- Implements `name = "llm_generate"`
- Provides clear description: "Use the LLM to generate natural language text based on a prompt. Useful for: formulating user responses, summarizing information, formatting data, translating content, creative writing."
- Defines `parameters_schema` with:
  - `prompt` (str, required): The prompt for the LLM
  - `context` (object, optional): Structured data to include as context
  - `max_tokens` (int, optional, default=500): Maximum response length
  - `temperature` (float, optional, default=0.7): Creativity control

**AC1.3.1.2:** The `execute(**kwargs)` async method:
- Accepts: prompt, context (optional), max_tokens, temperature
- Constructs full prompt by combining context (if provided) with the prompt text
- Calls the agent's LLM instance with appropriate parameters
- Returns structured result:
```python
{
  "success": True,
  "generated_text": "...",
  "tokens_used": 234,
  "prompt_tokens": 150,
  "completion_tokens": 84
}
```

**AC1.3.1.3:** Context handling:
- If `context` dict is provided, format it clearly in the prompt (JSON or human-readable)
- Allow agent to pass structured data (e.g., list of documents, search results) for synthesis
- Context should be serializable and logged for debugging

**AC1.3.1.4:** Error handling:
- LLM API failures caught and returned as `{"success": False, "error": "...", "type": "LLMError"}`
- Token limit exceeded handled gracefully with truncation hint
- Network timeouts handled with retry suggestions

**AC1.3.1.5:** Structured logging with structlog:
- Logs: `tool="llm_generate"`, `prompt_length`, `context_size`, `tokens_used`, `latency_ms`
- Does NOT log full prompt/response (privacy) - only metadata

**AC1.3.1.6:** The tool is **agent-agnostic** and works for:
- RAG agents (formulating answers after document retrieval)
- Git agents (summarizing commit history)
- File agents (explaining file content)
- Any agent needing text generation capability

**AC1.3.1.7:** Unit tests with mocked LLM verify:
- Successful text generation returns proper format
- Context is correctly integrated into prompt
- Token limits are respected
- Errors are handled gracefully
- Logging captures metadata without exposing sensitive data

**AC1.3.1.8:** Integration test demonstrates:
- LLMTool can be registered alongside other tools
- Agent can call llm_generate within a TodoList workflow
- Generated text is properly returned and can be used in subsequent steps

#### Example Usage in TodoList

**Scenario: User asks "Which documents are available?"**

```
TodoList:
1. Retrieve document list
   - Tool: rag_list_documents
   - Input: {"limit": 20}
   - Acceptance: Document list retrieved
   
2. Formulate response to user
   - Tool: llm_generate
   - Input: {
       "prompt": "Based on the retrieved documents, provide a clear, user-friendly answer to: 'Which documents are available?'",
       "context": {
         "documents": [
           {"title": "eGECKO-Personalzeitmanagement.pdf", "chunk_count": 214},
           {"title": "eGECKO-evo.pdf", "chunk_count": 15}
         ]
       }
     }
   - Acceptance: Natural language response generated
```

#### Design Considerations

**Why a separate LLM Tool vs ActionType.DONE?**
- ✅ **Explicit workflow visibility**: Response generation is a visible step in TodoList
- ✅ **Reusability**: Can be used for summaries, translations, formatting - not just final responses
- ✅ **Orchestration**: Agent can chain LLM calls (e.g., translate → summarize → respond)
- ✅ **Testability**: LLM calls are observable and testable like any tool
- ✅ **Flexibility**: Works for both interactive (chat) and autonomous (workflow) modes

**Why NOT use ActionType.DONE?**
- ActionType.DONE implies task completion, not text generation
- Doesn't fit autonomous workflows where no user response is needed
- Less flexible for multi-step text generation tasks

#### Integration Verification

- **IV1.3.1.1:** LLMTool registers successfully in Agent.create_agent() and Agent.create_rag_agent()
- **IV1.3.1.2:** Agent can execute TodoItems calling llm_generate
- **IV1.3.1.3:** Tool works alongside all existing tools without conflicts
- **IV1.3.1.4:** RAG agent can successfully complete "list documents → respond to user" workflow
- **IV1.3.1.5:** Existing agent functionality unaffected (non-LLM missions work identically)
- **IV1.3.1.6:** Tool execution respects agent's configured LLM instance and parameters

#### Technical Notes

**Implementation:**
- The tool should use the agent's existing LLM instance (passed during initialization)
- Token counting should use the LLM's tokenizer for accuracy
- Consider adding a `format` parameter in future for structured outputs (JSON, markdown, etc.)

**Prompt Construction:**
```python
if context:
    full_prompt = f"""Context Data:
{json.dumps(context, indent=2)}

Task: {prompt}
"""
else:
    full_prompt = prompt
```

**Future Enhancements (out of scope for this story):**
- Streaming support for long-form generation
- Multiple response variants for A/B testing
- Prompt templates for common patterns
- Function calling / structured output modes

---

### Story 1.4: RAG System Prompt for Query Classification and Planning

**As a** product manager defining agent behavior,
**I want** a comprehensive RAG-specific system prompt,
**so that** the agent intelligently classifies queries and generates optimal plans for knowledge retrieval tasks.

#### Acceptance Criteria

**AC1.4.1:** A new file `prompts/rag_system_prompt.py` exists containing `RAG_SYSTEM_PROMPT` string that includes:
- **Query Classification Section**: Instructions to classify queries as LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON
- **Planning Patterns Section**: Examples of typical TodoList structures for each query type (including final response step using llm_generate)
- **Clarification Guidelines**: When to ask for user input (ambiguous document references, missing filters)
- **Tool Usage Rules**: When to use rag_semantic_search vs rag_list_documents vs rag_get_document vs llm_generate
- **Response Generation Guidelines**: When and how to use llm_generate to formulate user-facing responses (interactive queries) vs when to skip responses (autonomous workflows)
- **Synthesis Instructions**: How to combine text and image blocks into markdown with citations
- **Source Citation Format**: Requirement to cite as "(Source: filename.pdf, S. X)"

**AC1.4.2:** The prompt includes **concrete examples** for each query type:
```
Example - LISTING (Interactive Query):
User: "Which documents are available?"
Plan:
1. List all documents (tool: rag_list_documents, acceptance: Document list retrieved)
2. Formulate response to user (tool: llm_generate with context, acceptance: Natural language response provided)

Example - CONTENT_SEARCH:
User: "How does the XYZ pump work?"
Plan:
1. Search for content about XYZ pump functionality (tool: rag_semantic_search, acceptance: ≥3 relevant blocks retrieved)
2. Synthesize results into markdown response (tool: llm_generate or PythonTool, acceptance: Response includes text + images + citations)

Example - AUTONOMOUS WORKFLOW (No user response):
Mission: "Index all PDFs in shared folder"
Plan:
1. Scan directory for PDFs (tool: file_tool)
2. Extract metadata from each PDF (tool: PythonTool)
3. Upload to Azure index (tool: rag_upload - future)
(No response step - workflow completes silently)
```

**AC1.4.3:** The prompt specifies **multimodal response format**:
- Embed images using `![caption](url)` markdown syntax
- Include source after each fact: "(Source: manual.pdf, S. 12)"
- Prioritize showing diagrams when available

**AC1.4.4:** The prompt is **parameterizable** - accepts variables like available_tools list, user_context details

**AC1.4.5:** Documentation in prompts/README.md explains:
- How to use the RAG prompt vs GENERIC_SYSTEM_PROMPT
- How to customize for specific domains
- Query classification logic

**AC1.4.6:** Unit test verifies prompt structure (contains required sections, valid Python string)

#### Integration Verification

- **IV1.4.1:** Agent initialized with RAG_SYSTEM_PROMPT successfully replaces GENERIC_SYSTEM_PROMPT
- **IV1.4.2:** TodoListManager generates RAG-appropriate plans when using RAG prompt
- **IV1.4.3:** Existing GENERIC_SYSTEM_PROMPT still works for non-RAG missions (no breaking changes)

---

### Story 1.5: Multimodal Synthesis via PythonTool

**As a** RAG-enabled agent,
**I want** to synthesize retrieved content blocks into cohesive markdown responses,
**so that** users receive complete answers with embedded images and proper citations without opening source documents.

#### Acceptance Criteria

**AC1.5.1:** The RAG system prompt (from Story 1.4) includes a **synthesis step template** that instructs the agent to:
- Use the existing `PythonTool` (tools/code_tool.py)
- Pass retrieved content blocks via the `context` parameter
- Execute Python code that formats markdown

**AC1.5.2:** A reference synthesis script is documented in `docs/rag_synthesis_example.py`:
```python
# Example synthesis code that agent would generate
def synthesize_response(blocks, query):
    markdown = f"# Answer to: {query}\n\n"
    for block in blocks:
        if block['block_type'] == 'text':
            markdown += f"{block['content']}\n\n"
            markdown += f"*(Source: {block['filename']}, S. {block['page_number']})*\n\n"
        elif block['block_type'] == 'image':
            markdown += f"![{block['image_caption']}]({block['image_url']})\n\n"
            markdown += f"*(Source: {block['filename']}, S. {block['page_number']})*\n\n"
    return markdown
```

**AC1.5.3:** The RAG system prompt instructs the agent to:
- Generate synthesis code dynamically based on retrieved results
- Handle mixed text/image blocks appropriately
- Ensure all sources are cited
- Return the final markdown string

**AC1.5.4:** Integration test demonstrates:
- Agent receives RAG mission: "Explain the XYZ process"
- TodoList includes: Step 1 (search), Step 2 (synthesize with PythonTool)
- Final response contains both text and embedded image markdown
- All content includes source citations

**AC1.5.5:** The synthesis approach leverages **existing PythonTool context parameter** (no new tool needed)

#### Integration Verification

- **IV1.5.1:** Existing PythonTool (tools/code_tool.py) works without modification for synthesis
- **IV1.5.2:** Agent successfully executes synthesis step using PythonTool
- **IV1.5.3:** Final markdown output is valid and renders correctly in markdown viewers

---

### Story 1.6: RAG Agent Factory Method and End-to-End Integration

**As a** developer using the agent framework,
**I want** a simple factory method to create a RAG-enabled agent,
**so that** I can quickly instantiate an agent with all RAG tools and the appropriate system prompt without manual configuration.

#### Acceptance Criteria

**AC1.6.1:** A new static method exists in `agent.py`:
```python
@staticmethod
def create_rag_agent(
    name: str,
    description: str,
    mission: str,
    work_dir: str,
    llm,
    user_context: Optional[Dict] = None
) -> "Agent"
```

**AC1.6.2:** The method:
- Loads Azure configuration from environment variables (validates at startup)
- Instantiates all RAG tools: SemanticSearchTool, ListDocumentsTool, GetDocumentTool, LLMTool
- Includes all existing tools (Web, File, Git, Python, etc.)
- Sets system_prompt to RAG_SYSTEM_PROMPT (from prompts/rag_system_prompt.py)
- Passes user_context to RAG-specific tools and llm instance to LLMTool
- Creates TodoListManager and StateManager per existing pattern
- Returns fully configured Agent instance

**AC1.6.3:** Example usage documented in README:
```python
from capstone.agent_v2.agent import Agent

agent = Agent.create_rag_agent(
    name="RAG Assistant",
    description="Multimodal knowledge retrieval agent",
    mission="Explain how the safety valve works",
    work_dir="./rag_sessions",
    llm=None,
    user_context={"user_id": "user123", "department": "engineering"}
)

async for event in agent.execute(user_message="Start", session_id="session-1"):
    if event.type == AgentEventType.COMPLETE:
        print(event.data["todolist"])
```

**AC1.6.4:** Integration test demonstrates full RAG workflow:
- Create RAG agent using factory method
- Execute mission: "What are the main risks in Project Titan from Q3 reports?"
- Agent classifies as CONTENT_SEARCH
- TodoList includes: search → synthesize → respond steps
- Agent calls rag_semantic_search with proper filters
- Agent calls PythonTool or llm_generate for synthesis
- Agent calls llm_generate to formulate final user response
- Final response includes text + images + citations
- All events stream correctly (THOUGHT, TOOL_RESULT, COMPLETE)

**AC1.6.5:** Backward compatibility test:
- Existing `Agent.create_agent()` method unchanged
- Non-RAG agents continue to work identically
- Both factory methods can coexist

**AC1.6.6:** Error scenarios handled:
- Missing Azure environment variables → Clear error message with setup instructions
- Invalid credentials → Azure SDK error caught and reported
- Empty search results → Agent handles gracefully (returns "No results found")

#### Integration Verification

- **IV1.6.1:** All existing agent tests pass (no regressions from adding RAG tools)
- **IV1.6.2:** RAG agent can execute both RAG missions and generic missions (tool flexibility)
- **IV1.6.3:** StateManager persists RAG session state correctly (backward compatible)
- **IV1.6.4:** Performance: RAG agent initialization completes in <1 second
- **IV1.6.5:** Security: User context properly enforced in all Azure queries

---

