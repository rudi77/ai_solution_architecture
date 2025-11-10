# Story 1.3.1: Generic LLM Tool for Response Generation - Brownfield Addition

## User Story

**As a** agent framework developer,
**I want** a generic LLM tool that enables any agent to generate natural language text,
**So that** agents can formulate responses to users, create summaries, and perform text generation tasks as explicit tool actions within their workflow.

## Story Context

**Business Context:**
After retrieving data via tools (e.g., rag_list_documents, web_search, file_read), agents need a way to formulate natural language responses to users. Currently, agents have no tool-based mechanism for text generation, leading to incomplete interactions where tool results are returned but no human-readable response is provided to users.

This creates a workflow gap, especially for interactive chat scenarios where users expect natural language answers, not raw tool outputs.

**Existing System Integration:**

- **Integrates with:** Agent framework Tool base class (tools/tool.py), Agent.llm instance
- **Technology:** Python 3.11+, async/await, structlog
- **Follows pattern:** Existing Tool inheritance pattern (same as WebSearchTool, FileReadTool, etc.)
- **Touch points:**
  - Agent.create_agent() and Agent.create_rag_agent() tool registration
  - Agent.llm instance for text generation
  - TodoList workflow execution
  - AgentEvent streaming for tool results

**Dependencies:**
- ✅ No story dependencies - this is a standalone core tool
- ✅ Works with existing Agent.llm instance (already available in framework)
- ✅ Compatible with all existing tools and agents

**Important Design Decision:**
- This tool makes text generation an **explicit workflow step** (visible in TodoList)
- Alternative approaches considered:
  - ❌ ActionType.DONE with summary → Not suitable for autonomous workflows
  - ❌ Automatic response generation → Lacks flexibility and transparency
  - ✅ **Tool-based approach** → Maximum flexibility, visibility, and reusability

## Acceptance Criteria

### Functional Requirements

**AC1.3.1.1: LLMTool Implementation**

A new tool `LLMTool` exists in `tools/llm_tool.py` that:
- Inherits from `Tool` base class (tools/tool.py)
- Implements `name = "llm_generate"`
- Implements `description` clearly explaining: "Use the LLM to generate natural language text based on a prompt. Useful for: formulating user responses, summarizing information, formatting data, translating content, creative writing."
- Defines `parameters_schema` with:
  - `prompt` (string, required) - The prompt/instruction for the LLM
  - `context` (object, optional) - Structured data to include as context (e.g., search results, document lists)
  - `max_tokens` (integer, optional, default=500) - Maximum response length
  - `temperature` (number, optional, default=0.7) - Creativity control (0.0-1.0)
- Accepts an `llm` instance during initialization (the agent's configured LLM)

**AC1.3.1.2: Execute Method Implementation**

The `execute(**kwargs)` async method:
- Accepts parameters: `prompt`, `context` (optional), `max_tokens` (optional), `temperature` (optional)
- If `context` is provided:
  - Formats it as JSON or human-readable text
  - Constructs full prompt: `Context Data:\n{context}\n\nTask: {prompt}`
- If no `context`:
  - Uses prompt directly
- Calls `self.llm.generate()` with:
  - The constructed prompt
  - `max_tokens` parameter
  - `temperature` parameter
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

**AC1.3.1.3: Error Handling**

Error scenarios are handled gracefully:
- **LLM API failures**: Caught and returned as `{"success": False, "error": "...", "type": "LLMError", "hints": ["Check LLM configuration", "Verify API credentials"]}`
- **Token limit exceeded**: Handled with clear error message and hint to reduce prompt or increase max_tokens
- **Network timeouts**: Caught and returned with retry suggestion
- **Invalid parameters**: Validated and clear error messages provided
- All errors are logged with structured logging

**AC1.3.1.4: Context Serialization**

Context handling supports multiple formats:
- **Dict/List**: Serialized to clean JSON format with indentation
- **String**: Used directly
- **Nested structures**: Properly serialized (handles lists of dicts, etc.)
- **Size limits**: Large contexts (>2000 chars) are logged with warning
- **Sanitization**: Context is JSON-serializable and safe for logging

Example context formatting:
```python
context = {
    "documents": [
        {"title": "doc1.pdf", "chunks": 214},
        {"title": "doc2.pdf", "chunks": 15}
    ]
}

# Formatted in prompt as:
"""
Context Data:
{
  "documents": [
    {"title": "doc1.pdf", "chunks": 214},
    {"title": "doc2.pdf", "chunks": 15}
  ]
}

Task: Provide a user-friendly answer listing these documents
"""
```

**AC1.3.1.5: Structured Logging**

Using structlog, the tool logs:
- **On execute start**: `event="llm_generate_started"`, `tool="llm_generate"`, `prompt_length=X`, `has_context=True/False`, `context_size=Y`
- **On success**: `event="llm_generate_completed"`, `tokens_used=X`, `prompt_tokens=Y`, `completion_tokens=Z`, `latency_ms=W`
- **On error**: `event="llm_generate_failed"`, `error_type="..."`, `error="..."`, `latency_ms=X`
- **Privacy**: Does NOT log full prompt or generated text (only lengths/metadata)
- **Debug mode**: Optionally logs first 100 chars of prompt/response when debug=True

**AC1.3.1.6: Agent-Agnostic Design**

The tool works for all agent types:
- ✅ RAG agents (formulating answers after document retrieval)
- ✅ Git agents (summarizing commit history)
- ✅ File agents (explaining file content)
- ✅ Web agents (summarizing search results)
- ✅ Generic agents (any text generation task)

No RAG-specific logic or assumptions are hardcoded.

### Non-Functional Requirements

**AC1.3.1.7: Performance**

- Text generation latency depends on LLM provider (typically 1-5 seconds)
- Tool overhead (prompt construction, logging) is < 50ms
- No blocking operations - fully async/await compliant
- Token counting uses efficient tokenizer (if available) or approximation

**AC1.3.1.8: Security & Privacy**

- Generated text is NOT logged in full (only metadata)
- Context data is NOT logged in full (only size)
- Sensitive data in context is handled safely (no exposure in logs)
- Optional debug mode requires explicit activation
- LLM API credentials are handled by existing LLM instance (no duplicate handling)

### Testing Requirements

**AC1.3.1.9: Unit Tests**

Unit tests exist in `tests/test_llm_tool.py` with mocked LLM covering:

1. **Successful generation without context**:
   - Mock LLM returns text
   - Verify success=True, generated_text present, tokens_used calculated
   - Verify prompt passed correctly to LLM

2. **Successful generation with context**:
   - Provide context dict
   - Verify context is formatted and included in prompt
   - Verify JSON serialization works

3. **Complex context structures**:
   - Nested dicts, lists of dicts
   - Verify proper serialization
   - Verify no JSON errors

4. **Parameter handling**:
   - Test max_tokens parameter passed to LLM
   - Test temperature parameter passed to LLM
   - Test default values used when not provided

5. **Error handling**:
   - Mock LLM raises exception
   - Verify error returned as dict with success=False
   - Verify error type and hints provided

6. **Token limit exceeded**:
   - Mock LLM raises token limit error
   - Verify graceful handling with appropriate hint

7. **Logging verification**:
   - Verify structured logs emitted
   - Verify metadata captured (not full text)
   - Verify privacy (no sensitive data in logs)

8. **Tool schema validation**:
   - Verify name="llm_generate"
   - Verify description is clear and helpful
   - Verify parameters_schema is valid JSON Schema

**AC1.3.1.10: Integration Tests**

Integration test in `tests/integration/test_llm_tool_integration.py`:

1. **LLMTool with real LLM**:
   - Create LLMTool with actual LLM instance
   - Execute simple prompt
   - Verify real text is generated
   - Verify token counts are accurate

2. **LLMTool in Agent workflow**:
   - Register LLMTool in Agent.create_agent()
   - Create TodoList with llm_generate step
   - Execute workflow
   - Verify tool is called and returns result

3. **RAG workflow integration**:
   - Agent.create_rag_agent() includes LLMTool
   - Execute "list documents → respond" workflow
   - Verify llm_generate is called with document context
   - Verify natural language response is generated

## Definition of Done

### Code Quality
- [ ] LLMTool class implemented in `tools/llm_tool.py`
- [ ] Inherits from Tool base class correctly
- [ ] All methods properly typed with type hints
- [ ] Docstrings for class and all public methods
- [ ] Follows existing code style (black, flake8)
- [ ] No linter errors or warnings

### Testing
- [ ] All 8 unit tests implemented and passing
- [ ] Integration test with real LLM passing
- [ ] Test coverage ≥ 90% for llm_tool.py
- [ ] Edge cases covered (empty prompts, large contexts, etc.)

### Documentation
- [ ] Docstrings explain purpose and usage
- [ ] Example usage in docstring or comments
- [ ] README.md updated (if tools have a README)
- [ ] Story document updated with "Ready for Review" status

### Integration
- [ ] Tool imports without errors
- [ ] Tool can be registered in Agent.create_agent()
- [ ] Tool can be registered in Agent.create_rag_agent()
- [ ] Tool works alongside all existing tools (no conflicts)
- [ ] All existing agent tests still pass (no regressions)

### Logging & Monitoring
- [ ] Structured logging implemented with structlog
- [ ] Privacy-safe logging (no sensitive data exposure)
- [ ] Latency and token usage tracked
- [ ] Errors logged with sufficient context for debugging

## Integration Verification

After implementation, verify:

- **IV1.3.1.1:** LLMTool registers successfully in Agent.create_agent() and Agent.create_rag_agent()
- **IV1.3.1.2:** Agent can execute TodoItems calling llm_generate
- **IV1.3.1.3:** Tool works alongside all existing tools without conflicts
- **IV1.3.1.4:** RAG agent can successfully complete "list documents → respond to user" workflow
- **IV1.3.1.5:** Git agent can use llm_generate to summarize commits
- **IV1.3.1.6:** Existing agent functionality unaffected (non-LLM missions work identically)
- **IV1.3.1.7:** Tool execution respects agent's configured LLM instance and parameters
- **IV1.3.1.8:** No performance degradation in existing workflows

## Example Usage Scenarios

### Scenario 1: RAG Agent Document Listing

```python
# TodoList generated by agent for: "Welche Dokumente gibt es?"
TodoList:
1. Retrieve document list
   - Tool: rag_list_documents
   - Input: {"limit": 20}
   - Acceptance: Document list retrieved
   
2. Formulate response to user
   - Tool: llm_generate
   - Input: {
       "prompt": "Based on the retrieved documents, provide a clear, user-friendly answer to the question 'Welche Dokumente gibt es?'",
       "context": {
         "documents": [
           {"document_id": "...", "document_title": "eGECKO-Personalzeitmanagement.pdf", "chunk_count": 214},
           {"document_id": "...", "document_title": "eGECKO-evo.pdf", "chunk_count": 15}
         ]
       }
     }
   - Acceptance: Natural language response generated
```

**Expected Output:**
```json
{
  "success": true,
  "generated_text": "Es gibt 2 Dokumente in Ihrer Wissensdatenbank:\n\n1. eGECKO-Personalzeitmanagement.pdf (214 Seiten)\n2. eGECKO-evo.pdf (15 Seiten)\n\nMöchten Sie mehr Details zu einem dieser Dokumente erfahren?",
  "tokens_used": 145,
  "prompt_tokens": 98,
  "completion_tokens": 47
}
```

### Scenario 2: Git Agent Commit Summary

```python
# TodoList for: "Summarize last week's commits"
TodoList:
1. Retrieve commit history
   - Tool: git_log
   - Input: {"since": "1 week ago"}
   
2. Summarize commits
   - Tool: llm_generate
   - Input: {
       "prompt": "Summarize these commits in a brief, user-friendly format highlighting main changes",
       "context": {
         "commits": [
           {"hash": "abc123", "message": "Fix bug in auth", "author": "John"},
           {"hash": "def456", "message": "Add new feature X", "author": "Jane"}
         ]
       }
     }
```

### Scenario 3: Web Agent Search Summary

```python
# TodoList for: "What's new in Python 3.13?"
TodoList:
1. Search web
   - Tool: web_search
   - Input: {"query": "Python 3.13 new features"}
   
2. Synthesize findings
   - Tool: llm_generate
   - Input: {
       "prompt": "Synthesize these search results into a concise summary of Python 3.13's new features",
       "context": {
         "search_results": [...]
       }
     }
```

## Technical Notes

### Implementation Details

**Prompt Construction:**
```python
async def execute(self, prompt: str, context: Optional[Dict] = None, 
                  max_tokens: int = 500, temperature: float = 0.7) -> Dict[str, Any]:
    """Execute LLM text generation."""
    
    # Build full prompt
    if context:
        context_str = json.dumps(context, indent=2, ensure_ascii=False)
        full_prompt = f"""Context Data:
{context_str}

Task: {prompt}
"""
    else:
        full_prompt = prompt
    
    # Log metadata only
    self.logger.info(
        "llm_generate_started",
        prompt_length=len(full_prompt),
        has_context=context is not None,
        context_size=len(context_str) if context else 0
    )
    
    # Call LLM
    start_time = time.time()
    try:
        response = await self.llm.generate(
            prompt=full_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Extract text and token counts
        generated_text = response.get("text") or response.get("content")
        tokens_used = response.get("usage", {}).get("total_tokens", 0)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        self.logger.info(
            "llm_generate_completed",
            tokens_used=tokens_used,
            latency_ms=latency_ms
        )
        
        return {
            "success": True,
            "generated_text": generated_text,
            "tokens_used": tokens_used,
            "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": response.get("usage", {}).get("completion_tokens", 0)
        }
    
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        self.logger.error(
            "llm_generate_failed",
            error_type=type(e).__name__,
            error=str(e)[:200],
            latency_ms=latency_ms
        )
        
        return {
            "success": False,
            "error": str(e),
            "type": "LLMError",
            "hints": ["Check LLM configuration", "Verify API credentials", "Reduce prompt size if token limit exceeded"]
        }
```

**LLM Instance Access:**
```python
class LLMTool(Tool):
    def __init__(self, llm):
        """Initialize with agent's LLM instance."""
        self.llm = llm
        self.logger = structlog.get_logger()
```

**Agent Integration:**
```python
# In Agent.create_rag_agent():
tools = [
    SemanticSearchTool(user_context=user_context),
    ListDocumentsTool(user_context=user_context),
    GetDocumentTool(user_context=user_context),
    LLMTool(llm=llm),  # ← Add LLMTool
    WebSearchTool(),
    FileReadTool(),
    # ... other tools
]
```

### Future Enhancements (Out of Scope)

These are explicitly NOT part of this story but could be future work:

- Streaming support for long-form generation (yield chunks)
- Multiple response variants for A/B testing
- Prompt templates library for common patterns
- Function calling / structured output modes
- Fine-grained control over LLM parameters (top_p, frequency_penalty, etc.)
- Support for multiple LLM providers (fallback mechanisms)
- Caching of common prompts/responses
- Rate limiting and quota management

### Risk Assessment

**Low Risk:**
- ✅ No external dependencies beyond existing LLM
- ✅ No schema changes
- ✅ No breaking changes to existing code
- ✅ Isolated implementation (new file)

**Considerations:**
- ⚠️ LLM latency is variable (depends on provider, load)
- ⚠️ Token costs should be monitored in production
- ⚠️ Large contexts may exceed token limits → need good error messages

## Dependencies & Prerequisites

**Required for Development:**
- ✅ Agent framework with Tool base class (already exists)
- ✅ Agent.llm instance configured (already exists)
- ✅ structlog for logging (already installed)
- ✅ Python 3.11+ with async/await support

**No External Dependencies:**
- No new Python packages required
- No Azure or cloud service dependencies
- Works with any LLM that has a generate() method

## Status

**Current Status:** Draft

**Next Steps:**
1. Review story with team
2. Estimate development effort (expected: 1-2 days)
3. Implement LLMTool
4. Write tests
5. Update Story 1.4 (RAG System Prompt) to reference llm_generate in planning patterns

---

## Dev Agent Record

**Status:** Not Started

**Agent Model Used:** N/A

**File List:**
- Created: (will be filled during implementation)
- Modified: (will be filled during implementation)

**Change Log:**
- (will be filled during implementation)

**Debug Log References:**
- (will be filled during implementation)

**Completion Notes:**
- (will be filled after implementation)

---

## QA Results

**Status:** Not Reviewed

**QA Agent:** N/A

**Review Date:** N/A

**Findings:**
- (will be filled during QA review)

**Final Status:** N/A

