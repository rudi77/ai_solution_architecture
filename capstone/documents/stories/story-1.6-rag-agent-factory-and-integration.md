# Story 1.6: RAG Agent Factory Method and End-to-End Integration - Brownfield Addition

## User Story

**As a** developer using the agent framework,
**I want** a simple factory method to create a RAG-enabled agent,
**So that** I can quickly instantiate an agent with all RAG tools and the appropriate system prompt without manual configuration.

## Story Context

**Business Context:**
Creating a RAG agent currently requires manual assembly of multiple components:
- Instantiating each RAG tool individually (SemanticSearchTool, ListDocumentsTool, GetDocumentTool, LLMTool)
- Loading and validating Azure configuration
- Setting RAG_SYSTEM_PROMPT
- Configuring user context for security filtering
- Combining with existing tools (Web, File, Python, etc.)

This complexity creates barriers to adoption and increases the likelihood of configuration errors. A factory method abstracts this complexity, providing a one-line solution to create fully-configured RAG agents.

**Existing System Integration:**

- **Integrates with:** Agent class, all RAG tools from Stories 1.1-1.3.1, RAG_SYSTEM_PROMPT from Story 1.4
- **Technology:** Python static method, factory pattern
- **Follows pattern:** Similar to existing Agent.create_agent() (if exists)
- **Touch points:**
  - Agent class gains create_rag_agent() static method
  - All RAG tools registered automatically
  - Azure configuration validated at agent creation
  - User context passed to relevant tools

**Dependencies:**
- ✅ Story 1.1 complete (AzureSearchBase with Azure configuration)
- ✅ Story 1.2 complete (SemanticSearchTool)
- ✅ Story 1.3 complete (ListDocumentsTool, GetDocumentTool)
- ✅ Story 1.3.1 complete (LLMTool)
- ✅ Story 1.4 complete (RAG_SYSTEM_PROMPT)
- ✅ All prior stories fully functional

**Important Design Decision:**
- Factory method is **additive** - Agent.create_agent() unchanged
- Backward compatibility maintained - non-RAG agents unaffected
- Sensible defaults with customization options
- Fail-fast validation of Azure configuration

## Acceptance Criteria

### Functional Requirements

**AC1.6.1: Factory Method Signature**

A new static method exists in `agent.py`:

```python
@staticmethod
def create_rag_agent(
    name: str,
    description: str,
    mission: str,
    work_dir: str,
    llm,
    user_context: Optional[Dict[str, Any]] = None,
    include_standard_tools: bool = True,
    azure_config: Optional[Dict[str, str]] = None
) -> "Agent":
    """
    Create a RAG-enabled agent with Azure AI Search tools and RAG system prompt.
    
    This factory method automatically:
    - Loads and validates Azure Search configuration
    - Instantiates all RAG tools (semantic search, document tools, LLM tool)
    - Optionally includes standard tools (Web, File, Git, Python)
    - Sets RAG_SYSTEM_PROMPT for intelligent query handling
    - Configures user context for security filtering
    
    Args:
        name: Agent name (e.g., "RAG Knowledge Assistant")
        description: Agent description for logging/UI
        mission: Agent's primary mission/task
        work_dir: Working directory for agent state/files
        llm: LLM instance for agent reasoning and llm_generate tool
        user_context: Optional dict with user_id, org_id, scope for security filtering
        include_standard_tools: If True, include Web, File, Git, Python tools (default: True)
        azure_config: Optional Azure config override (for testing)
            Keys: endpoint, api_key, content_index, documents_index
    
    Returns:
        Fully configured Agent instance with RAG capabilities
    
    Raises:
        ValueError: If Azure configuration is missing or invalid
        
    Example:
        >>> agent = Agent.create_rag_agent(
        ...     name="Knowledge Assistant",
        ...     description="Multimodal RAG agent for technical docs",
        ...     mission="Answer user questions about technical documentation",
        ...     work_dir="./rag_sessions",
        ...     llm=my_llm_instance,
        ...     user_context={"user_id": "user123", "org_id": "acme-corp", "scope": "shared"}
        ... )
        >>> # Agent ready to use with all RAG capabilities
    """
```

**AC1.6.2: Factory Method Implementation**

The method performs these steps:

1. **Validate Azure Configuration** (fail-fast):
   ```python
   # Try to create AzureSearchBase to validate config
   try:
       azure_base = AzureSearchBase(config=azure_config)
   except ValueError as e:
       raise ValueError(f"Azure Search configuration invalid: {e}") from e
   ```

2. **Instantiate RAG Tools**:
   ```python
   rag_tools = [
       SemanticSearchTool(user_context=user_context),
       ListDocumentsTool(user_context=user_context),
       GetDocumentTool(user_context=user_context),
       LLMTool(llm=llm)
   ]
   ```

3. **Optionally Include Standard Tools**:
   ```python
   tools = rag_tools.copy()
   if include_standard_tools:
       tools.extend([
           WebSearchTool(),
           FileReadTool(),
           FileWriteTool(),
           GitTool(),
           PythonTool(),
           AskUserTool()
       ])
   ```

4. **Load RAG System Prompt**:
   ```python
   from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT
   ```

5. **Create and Return Agent**:
   ```python
   agent = Agent(
       name=name,
       description=description,
       system_prompt=RAG_SYSTEM_PROMPT,
       mission=mission,
       work_dir=work_dir,
       tools=tools,
       llm=llm
   )
   return agent
   ```

**AC1.6.3: Configuration Validation**

The factory method validates:
- ✅ Azure endpoint is set and valid URL
- ✅ Azure API key is set (non-empty)
- ✅ Index names are valid (if provided)
- ✅ user_context structure is valid (if provided)
- ❌ Raises clear ValueError with setup instructions if invalid

**AC1.6.4: Example Usage Documentation**

README.md includes complete example:

```python
from capstone.agent_v2.agent import Agent
from my_llm_provider import get_llm

# Create RAG agent with one line
agent = Agent.create_rag_agent(
    name="Technical Docs Assistant",
    description="RAG agent for answering questions about technical documentation",
    mission="Help users find and understand information from our technical docs",
    work_dir="./rag_sessions",
    llm=get_llm(),
    user_context={
        "user_id": "john.doe@acme.com",
        "org_id": "acme-corp",
        "scope": "shared"
    }
)

# Use agent in async context
async def answer_question(question: str):
    async for event in agent.execute(user_message=question, session_id="session-123"):
        if event.type == AgentEventType.THOUGHT:
            print(f"Thinking: {event.data['thought']}")
        elif event.type == AgentEventType.TOOL_RESULT:
            print(f"Tool result: {event.data}")
        elif event.type == AgentEventType.COMPLETE:
            print(f"Final answer: {event.data.get('message', 'Task complete')}")

# Example questions
await answer_question("Which technical manuals are available?")
await answer_question("How does the XYZ component work?")
await answer_question("Summarize the safety manual")
```

**AC1.6.5: Error Scenarios Handled**

Factory method handles errors gracefully:

1. **Missing Azure env variables**:
   ```python
   raise ValueError("""
   Azure Search configuration missing. Please set:
     AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net
     AZURE_SEARCH_API_KEY=your-api-key
   Optional:
     AZURE_SEARCH_CONTENT_INDEX=content-blocks (default)
     AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata (default)
   """)
   ```

2. **Invalid credentials**:
   - Caught during AzureSearchBase initialization
   - Clear error message with troubleshooting hints

3. **Invalid user_context**:
   ```python
   if user_context and not isinstance(user_context, dict):
       raise ValueError("user_context must be a dict with keys: user_id, org_id, scope")
   ```

### Non-Functional Requirements

**AC1.6.6: Performance**

- RAG agent initialization completes in <1 second
- No network calls during initialization (lazy Azure connection)
- Tool registration is efficient (no overhead)

**AC1.6.7: Backward Compatibility**

- Existing Agent.create_agent() method unchanged (if it exists)
- Non-RAG agents unaffected by factory method addition
- Both factory methods can coexist
- No breaking changes to Agent class constructor

### Testing Requirements

**AC1.6.8: Unit Tests**

Unit tests in `tests/test_rag_agent_factory.py`:

1. **Factory method exists and is callable**
2. **Returns Agent instance**
3. **RAG tools are registered** (4 RAG tools + standard tools if enabled)
4. **RAG_SYSTEM_PROMPT is set**
5. **user_context passed to RAG tools**
6. **include_standard_tools parameter works**
7. **Azure config validation** (missing vars raise ValueError)
8. **Invalid user_context raises ValueError**

**AC1.6.9: Integration Tests**

Integration tests in `tests/integration/test_rag_end_to_end.py`:

1. **Complete LISTING workflow**:
   ```python
   agent = Agent.create_rag_agent(...)
   events = await agent.execute(
       user_message="Which documents are available?",
       session_id="test-123"
   )
   # Verify:
   # - TodoList created with rag_list_documents + llm_generate steps
   # - Tools executed successfully
   # - Final response contains document list
   ```

2. **Complete CONTENT_SEARCH workflow**:
   ```python
   events = await agent.execute(
       user_message="How does the safety valve work?",
       session_id="test-456"
   )
   # Verify:
   # - rag_semantic_search called
   # - llm_generate synthesizes results
   # - Response includes text + citations
   ```

3. **Complete DOCUMENT_SUMMARY workflow**:
   ```python
   events = await agent.execute(
       user_message="Summarize the installation manual",
       session_id="test-789"
   )
   # Verify:
   # - rag_list_documents → rag_get_document → llm_generate
   # - Summary provided
   ```

4. **Error handling**:
   - Missing Azure config → Clear error
   - Empty search results → Graceful handling
   - Invalid document ID → Appropriate error message

**AC1.6.10: Backward Compatibility Tests**

Test that existing functionality is unaffected:

```python
def test_backward_compatibility():
    # Original Agent.create_agent() still works (if exists)
    agent = Agent.create_agent(
        name="Test",
        description="Test",
        system_prompt="Test prompt",
        mission="Test",
        work_dir="./test",
        llm=None
    )
    assert agent is not None
    
    # Non-RAG agents work normally
    # RAG agents don't affect non-RAG functionality
```

## Definition of Done

### Code Implementation
- [ ] `Agent.create_rag_agent()` static method implemented in `agent.py`
- [ ] All RAG tools instantiated and registered
- [ ] RAG_SYSTEM_PROMPT imported and set
- [ ] Azure configuration validation implemented
- [ ] user_context passed to relevant tools
- [ ] include_standard_tools parameter functional
- [ ] Error handling for all failure scenarios
- [ ] Type hints for all parameters and return value
- [ ] Comprehensive docstring with example

### Documentation
- [ ] README.md updated with RAG agent usage example
- [ ] Docstring explains all parameters and usage
- [ ] Error messages provide clear setup instructions
- [ ] Example code demonstrates common use cases
- [ ] Migration guide from manual assembly to factory (if applicable)

### Testing
- [ ] 8+ unit tests covering factory method functionality
- [ ] 4+ integration tests demonstrating end-to-end workflows
- [ ] All workflow types tested (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY)
- [ ] Error scenarios tested (missing config, invalid params)
- [ ] Backward compatibility verified
- [ ] All tests passing

### Integration
- [ ] Factory method creates fully functional RAG agent
- [ ] Agent can execute all RAG query types successfully
- [ ] Tools are properly registered and accessible
- [ ] RAG_SYSTEM_PROMPT correctly guides agent behavior
- [ ] Security filtering works with user_context
- [ ] Existing Agent functionality unaffected

### Quality
- [ ] Code follows project style guidelines
- [ ] No linter errors or warnings
- [ ] Performance requirements met (<1s initialization)
- [ ] Clear error messages for all failure modes
- [ ] No breaking changes introduced

## Integration Verification

After implementation, verify:

- **IV1.6.1:** All existing agent tests pass (no regressions)
- **IV1.6.2:** RAG agent can execute both RAG missions and generic missions
- **IV1.6.3:** StateManager persists RAG session state correctly
- **IV1.6.4:** TodoListManager generates RAG-appropriate plans with RAG_SYSTEM_PROMPT
- **IV1.6.5:** Performance: RAG agent initialization <1 second
- **IV1.6.6:** Security: User context properly enforced in all Azure queries
- **IV1.6.7:** Complete end-to-end workflow succeeds (query → plan → execute → respond)
- **IV1.6.8:** All tool types work correctly (RAG + standard tools)

## Technical Notes

### Implementation Location

```python
# In capstone/agent_v2/agent.py

class Agent:
    # ... existing methods ...
    
    @staticmethod
    def create_rag_agent(
        name: str,
        description: str,
        mission: str,
        work_dir: str,
        llm,
        user_context: Optional[Dict[str, Any]] = None,
        include_standard_tools: bool = True,
        azure_config: Optional[Dict[str, str]] = None
    ) -> "Agent":
        """Create RAG-enabled agent with all necessary tools and prompt."""
        # Implementation here
        pass
```

### Tool Registration Order

```python
# RAG tools first (specialized)
rag_tools = [
    SemanticSearchTool(user_context=user_context),  # Story 1.2
    ListDocumentsTool(user_context=user_context),   # Story 1.3
    GetDocumentTool(user_context=user_context),     # Story 1.3
    LLMTool(llm=llm)                                # Story 1.3.1
]

# Standard tools (if included)
standard_tools = [
    WebSearchTool(),      # Web search capability
    FileReadTool(),       # File operations
    FileWriteTool(),
    GitTool(),            # Git operations
    PythonTool(),         # Code execution
    AskUserTool()         # User interaction
]

all_tools = rag_tools + (standard_tools if include_standard_tools else [])
```

### Configuration Precedence

1. **Explicit azure_config parameter** (highest priority) - for testing
2. **Environment variables** - production default
3. **Default values** - fallback for optional settings

```python
def _get_azure_config(azure_config: Optional[Dict] = None) -> Dict:
    if azure_config:
        return azure_config
    
    return {
        "endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
        "api_key": os.getenv("AZURE_SEARCH_API_KEY"),
        "content_index": os.getenv("AZURE_SEARCH_CONTENT_INDEX", "content-blocks"),
        "documents_index": os.getenv("AZURE_SEARCH_DOCUMENTS_INDEX", "documents-metadata")
    }
```

### Example Workflows to Test

**Workflow 1: Simple Document Listing**
```
User: "Welche Dokumente gibt es?"
Expected Flow:
1. Agent classifies as LISTING
2. TodoList: [rag_list_documents, llm_generate]
3. List documents → Formulate response
4. User receives natural language list
```

**Workflow 2: Technical Question**
```
User: "How does the safety valve work?"
Expected Flow:
1. Agent classifies as CONTENT_SEARCH
2. TodoList: [rag_semantic_search, llm_generate]
3. Search content → Synthesize with images
4. User receives comprehensive answer with diagrams
```

**Workflow 3: Document Summary**
```
User: "Summarize the Q3 financial report"
Expected Flow:
1. Agent classifies as DOCUMENT_SUMMARY
2. TodoList: [rag_list_documents (filter), rag_get_document, llm_generate]
3. Find report → Get details → Format summary
4. User receives summary
```

**Workflow 4: Clarification Needed**
```
User: "Tell me about the report"
Expected Flow:
1. Agent classifies as DOCUMENT_SUMMARY
2. TodoList: [rag_list_documents, ask_user]
3. Multiple reports found → Ask which one
4. User clarifies → Continue workflow
```

### Future Enhancements (Out of Scope)

- Agent templates for specific domains (medical, legal, technical)
- Multi-agent orchestration (RAG agent as sub-agent)
- Streaming response support
- Custom tool registration via factory parameters
- Agent configuration profiles (JSON/YAML files)
- Hot-reload of RAG_SYSTEM_PROMPT for iteration
- Metrics and monitoring integration

## Risk Assessment

**Low Risk:**
- ✅ Builds on fully-tested components from Stories 1.1-1.5
- ✅ Factory pattern is well-understood
- ✅ Backward compatible (additive only)
- ✅ Fail-fast validation prevents runtime errors

**Medium Risk:**
- ⚠️ End-to-end integration may reveal edge cases
- ⚠️ Performance optimization may be needed at scale
- ⚠️ Azure connectivity issues in production

**Mitigation:**
- Comprehensive integration testing
- Performance benchmarks
- Clear error messages and documentation
- Fallback mechanisms for Azure failures

## Dependencies & Prerequisites

**Required (All prior stories complete):**
- ✅ Story 1.1 (AzureSearchBase)
- ✅ Story 1.2 (SemanticSearchTool)
- ✅ Story 1.3 (ListDocumentsTool, GetDocumentTool)
- ✅ Story 1.3.1 (LLMTool)
- ✅ Story 1.4 (RAG_SYSTEM_PROMPT)
- ✅ Story 1.5 (Synthesis patterns - optional but recommended)
- ✅ Agent class constructor and core functionality
- ✅ TodoListManager, StateManager functional

**Optional:**
- ⚠️ Existing Agent.create_agent() method (for consistency)
- ⚠️ Standard tools (Web, File, Git, Python, AskUser)

## Status

**Current Status:** Ready for Implementation

**Next Steps:**
1. Implement Agent.create_rag_agent() static method
2. Add configuration validation logic
3. Write unit tests for factory method
4. Write integration tests for end-to-end workflows
5. Update README.md with usage examples
6. Verify backward compatibility
7. Performance testing and optimization

---

## Dev Agent Record

**Status:** Not Started

**Agent Model Used:** N/A

**File List:**
- Created: (will be filled during implementation)
- Modified: (will be filled during implementation)

**Change Log:**
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

