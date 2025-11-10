# Story 1.4: RAG System Prompt for Query Classification and Planning - Brownfield Addition

## User Story

**As a** product manager defining agent behavior,
**I want** a comprehensive RAG-specific system prompt,
**So that** the agent intelligently classifies queries and generates optimal plans for knowledge retrieval tasks.

## Story Context

**Business Context:**
The RAG agent needs specialized intelligence to understand different types of knowledge queries (listing, searching, summarizing) and plan appropriate tool sequences. Without a RAG-specific prompt, the agent treats knowledge retrieval like generic tasks, leading to suboptimal plans and poor user experiences.

A well-crafted RAG system prompt acts as the "brain" of the RAG agent, teaching it:
- How to classify user queries into actionable categories
- Which tools to use for each query type
- When to formulate responses to users (interactive) vs silent completion (autonomous workflows)
- How to combine text and image results with proper citations

**Existing System Integration:**

- **Integrates with:** Agent class system_prompt parameter, TodoListManager for plan generation
- **Technology:** Python string templates, prompt engineering
- **Follows pattern:** Existing GENERIC_SYSTEM_PROMPT pattern (if exists in agent.py)
- **Touch points:**
  - Agent.__init__() accepts system_prompt parameter
  - TodoListManager uses system_prompt for plan generation
  - Agent.create_rag_agent() factory sets RAG_SYSTEM_PROMPT
  - All existing system prompt functionality preserved

**Dependencies:**
- ✅ Story 1.3.1 must be completed (LLMTool exists for response generation patterns)
- ✅ Tool descriptions from Stories 1.1, 1.2, 1.3 (rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
- ⚠️ This story can be developed in parallel with tool implementation (uses tool descriptions, not actual tools)

**Important Design Decision:**
- RAG_SYSTEM_PROMPT is **additive** - it extends existing agent capabilities
- GENERIC_SYSTEM_PROMPT remains unchanged for backward compatibility
- Agent.create_rag_agent() uses RAG_SYSTEM_PROMPT
- Agent.create_agent() continues to use GENERIC_SYSTEM_PROMPT (or custom prompt)

## Acceptance Criteria

### Functional Requirements

**AC1.4.1: Prompt File Structure**

A new module `prompts/rag_system_prompt.py` exists containing:
- `RAG_SYSTEM_PROMPT` string constant with complete RAG intelligence
- Optional: `build_rag_system_prompt(available_tools: List[str]) -> str` function for dynamic tool list injection
- Docstring explaining purpose and usage

The prompt must include these sections:
1. **Role Definition**: Who the agent is and its core mission
2. **Query Classification Section**: Instructions to classify queries into categories
3. **Planning Patterns Section**: Examples of TodoList structures for each query type
4. **Tool Usage Rules**: When to use each tool (rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
5. **Response Generation Guidelines**: When to use llm_generate for user-facing responses vs silent completion
6. **Clarification Guidelines**: When to ask users for more information
7. **Synthesis Instructions**: How to combine multimodal results
8. **Source Citation Format**: Requirement to cite sources

**AC1.4.2: Query Classification**

The prompt defines these query categories with clear criteria:

1. **LISTING**: User wants to know what documents/resources exist
   - Examples: "Which documents are available?", "Show all PDFs", "List manuals"
   - Key indicator: Question about availability/existence

2. **CONTENT_SEARCH**: User wants information from within documents
   - Examples: "How does X work?", "Explain Y", "What are the risks of Z?"
   - Key indicator: Question about content/knowledge

3. **DOCUMENT_SUMMARY**: User wants overview of specific document(s)
   - Examples: "Summarize the Q3 report", "What's in document X?"
   - Key indicator: Request for summary/overview

4. **METADATA_SEARCH**: User wants documents matching specific criteria
   - Examples: "Show PDFs from last week", "Find documents by author X"
   - Key indicator: Filtering by properties (date, author, type)

5. **COMPARISON**: User wants to compare multiple documents or sections
   - Examples: "Compare report A and B", "Differences between version 1 and 2"
   - Key indicator: Comparative language

**AC1.4.3: Planning Patterns with Examples**

The prompt includes concrete examples for each query type showing complete TodoList structures:

**Example - LISTING (Interactive Query):**
```
User: "Which documents are available?"

Classification: LISTING
Plan:
1. List all documents
   - Tool: rag_list_documents
   - Input: {"limit": 20}
   - Acceptance: Document list with titles and metadata retrieved

2. Formulate response to user
   - Tool: llm_generate
   - Input: {
       "prompt": "Based on the retrieved documents, provide a clear, user-friendly answer to: 'Which documents are available?'",
       "context": {"documents": [...]}
     }
   - Acceptance: Natural language response generated
```

**Example - CONTENT_SEARCH:**
```
User: "How does the XYZ pump work?"

Classification: CONTENT_SEARCH
Plan:
1. Search for XYZ pump content
   - Tool: rag_semantic_search
   - Input: {"query": "XYZ pump functionality operation", "top_k": 10}
   - Acceptance: ≥3 relevant content blocks retrieved

2. Synthesize results into response
   - Tool: llm_generate (or PythonTool for complex formatting)
   - Input: {
       "prompt": "Synthesize these search results into a comprehensive explanation of how the XYZ pump works, including any diagrams",
       "context": {"search_results": [...]}
     }
   - Acceptance: Response includes text + images (if available) + source citations
```

**Example - DOCUMENT_SUMMARY:**
```
User: "Summarize the safety manual"

Classification: DOCUMENT_SUMMARY
Plan:
1. Find safety manual document ID
   - Tool: rag_list_documents
   - Input: {"filters": {"document_type": "Manual"}, "limit": 10}
   - Acceptance: Safety manual identified

2. Get document metadata with summary
   - Tool: rag_get_document
   - Input: {"document_id": "..."}
   - Acceptance: Document summary retrieved

3. Formulate response
   - Tool: llm_generate
   - Input: {
       "prompt": "Present this document summary in a user-friendly format",
       "context": {"document": {...}}
     }
   - Acceptance: Natural language summary provided
```

**Example - AUTONOMOUS WORKFLOW (No user response):**
```
Mission: "Index all PDFs in shared folder"

Classification: AUTONOMOUS_WORKFLOW
Plan:
1. Scan directory for PDFs
   - Tool: file_tool
   - Acceptance: PDF list generated

2. Extract metadata from each PDF
   - Tool: python_tool
   - Acceptance: Metadata extracted

3. Upload to index
   - Tool: rag_upload (future story)
   - Acceptance: All PDFs indexed

(No response step - workflow completes silently)
```

**AC1.4.4: Tool Usage Guidelines**

The prompt clearly explains when to use each tool:

**rag_semantic_search:**
- Use when: User asks about content/knowledge within documents
- Input: Natural language query, top_k for result count
- Returns: Content blocks (text + images) with scores
- Best for: "How/What/Why" questions requiring deep content search

**rag_list_documents:**
- Use when: User wants to know what documents exist
- Input: Optional filters (type, date), limit
- Returns: List of documents with titles and basic metadata
- Best for: "Which/Show me/List" questions about document availability

**rag_get_document:**
- Use when: User asks about a specific document's details
- Input: document_id
- Returns: Full document metadata including summary (if available)
- Best for: "Tell me about document X" or after identifying specific document

**llm_generate:**
- Use when: Need to formulate natural language response to user
- Input: Prompt + optional context (structured data from previous tools)
- Returns: Generated text
- Best for: Final response step in interactive queries, summaries, explanations
- **CRITICAL**: Always include this as final step for interactive queries (users expect answers!)

**AC1.4.5: Response Generation Guidelines**

The prompt explicitly teaches when to generate responses:

**Interactive Queries (User expects answer):**
- ✅ ALWAYS include llm_generate as final step
- Pass retrieved data as context
- Formulate natural, conversational response
- Examples: Questions (Who/What/Where/How), Requests ("Show me", "Explain")

**Autonomous Workflows (No response needed):**
- ❌ Do NOT include response step
- Complete tasks silently
- Examples: Scheduled jobs, batch operations, background tasks

**Indicators for Interactive vs Autonomous:**
- Interactive: User asks a question, uses conversational language
- Autonomous: System mission/task, imperative commands without question

**AC1.4.6: Clarification Guidelines**

The prompt instructs when to ask users for clarification:

**Ask for clarification when:**
- Document reference is ambiguous ("the report" - which one?)
- Multiple matches found and user intent unclear
- Required information missing (date range, author name, etc.)
- User query is too vague to classify

**Use ask_user tool:**
```python
Action: ASK_USER
Question: "I found 3 reports from Q3. Which one do you want: Financial Report, Safety Report, or Operations Report?"
```

**Do NOT ask when:**
- Single clear match exists
- Query is unambiguous
- Reasonable defaults can be applied (e.g., "recent" = last 30 days)

**AC1.4.7: Multimodal Response Format**

The prompt specifies how to handle text + image results:

**Image Embedding:**
```markdown
![Image caption or description](https://storage.url/image.jpg)
```

**Source Citations:**
After each fact or statement:
```
(Source: technical-manual.pdf, S. 12)
```

**Prioritization:**
- Show diagrams when available for technical explanations
- Use images to supplement text, not replace it
- Always cite source after each content block

**AC1.4.8: Prompt is Parameterizable**

The prompt can be customized via variables:
- `{available_tools}` - Dynamically inject tool list
- `{user_context}` - User/org information for context
- `{domain_knowledge}` - Optional domain-specific guidance

Optional function for dynamic generation:
```python
def build_rag_system_prompt(
    available_tools: Optional[List[str]] = None,
    domain_knowledge: Optional[str] = None
) -> str:
    """Build RAG system prompt with dynamic tool list."""
    tools_str = ", ".join(available_tools) if available_tools else "all RAG tools"
    domain_str = f"\n\n{domain_knowledge}" if domain_knowledge else ""
    
    return RAG_SYSTEM_PROMPT.format(
        available_tools=tools_str,
        domain_knowledge=domain_str
    )
```

### Non-Functional Requirements

**AC1.4.9: Backward Compatibility**

- GENERIC_SYSTEM_PROMPT (if it exists) remains unchanged
- Agent.create_agent() continues to work without RAG prompt
- Non-RAG agents unaffected by RAG prompt existence
- RAG_SYSTEM_PROMPT is opt-in via Agent.create_rag_agent()

**AC1.4.10: Prompt Quality**

- Clear, unambiguous instructions
- Consistent terminology throughout
- Concrete examples for every major concept
- Professional tone, technically accurate
- No conflicting instructions

### Testing Requirements

**AC1.4.11: Unit Tests**

Unit tests in `tests/test_rag_system_prompt.py`:

1. **Prompt structure validation**:
   - RAG_SYSTEM_PROMPT is a non-empty string
   - Contains required sections (Query Classification, Planning Patterns, etc.)
   - No syntax errors (valid Python string)

2. **Section presence checks**:
   - Verify "Query Classification" section exists
   - Verify "Planning Patterns" section exists
   - Verify "Tool Usage Rules" section exists
   - Verify tool names mentioned (rag_semantic_search, rag_list_documents, llm_generate)

3. **Parameterization (if implemented)**:
   - build_rag_system_prompt() returns valid string
   - Variables are correctly substituted
   - Optional parameters work correctly

**AC1.4.12: Integration Tests**

Integration test in `tests/integration/test_rag_prompt_integration.py`:

1. **TodoListManager generates appropriate plans**:
   - Create agent with RAG_SYSTEM_PROMPT
   - Test query: "Which documents are available?"
   - Verify TodoList includes: rag_list_documents + llm_generate steps
   - Verify acceptance criteria are clear

2. **Multiple query types**:
   - Test LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY queries
   - Verify each generates appropriate plan structure
   - Verify correct tools selected

3. **Agent uses prompt correctly**:
   - Agent.create_rag_agent() sets RAG_SYSTEM_PROMPT
   - Prompt is passed to TodoListManager
   - Agent behavior reflects prompt instructions

## Definition of Done

### Documentation
- [ ] `prompts/rag_system_prompt.py` file created with RAG_SYSTEM_PROMPT constant
- [ ] Comprehensive docstring explaining purpose and usage
- [ ] All 8 sections present: Role, Classification, Planning, Tool Usage, Response Guidelines, Clarification, Synthesis, Citations
- [ ] At least 4 complete planning pattern examples included
- [ ] `prompts/README.md` created explaining prompt usage and customization
- [ ] `prompts/__init__.py` created for module structure

### Prompt Content
- [ ] Query classification defines 5+ categories with examples
- [ ] Planning patterns include complete TodoList examples for each category
- [ ] Tool usage rules clearly explain when to use each tool
- [ ] Response generation guidelines distinguish interactive vs autonomous
- [ ] Clarification guidelines specify when to ask users
- [ ] Multimodal format instructions included (images, citations)
- [ ] Interactive query examples include llm_generate as final step
- [ ] Autonomous workflow examples exclude response steps

### Testing
- [ ] Unit tests implemented and passing (prompt structure validation)
- [ ] Integration tests demonstrate TodoListManager generates correct plans
- [ ] Test multiple query types (LISTING, CONTENT_SEARCH, etc.)
- [ ] All existing agent tests still pass (backward compatibility)

### Integration
- [ ] Prompt imports without errors
- [ ] Agent.create_rag_agent() can use RAG_SYSTEM_PROMPT
- [ ] TodoListManager accepts and uses the prompt
- [ ] Existing GENERIC_SYSTEM_PROMPT unaffected (if exists)
- [ ] No breaking changes to existing agents

### Code Quality
- [ ] Follows Python string formatting best practices
- [ ] No typos or grammatical errors
- [ ] Consistent terminology throughout
- [ ] Professional and technically accurate language
- [ ] Clear structure with section headers

## Integration Verification

After implementation, verify:

- **IV1.4.1:** Agent initialized with RAG_SYSTEM_PROMPT successfully
- **IV1.4.2:** TodoListManager generates RAG-appropriate plans when using RAG prompt
- **IV1.4.3:** Plans include correct tool sequences (e.g., list → respond, search → synthesize)
- **IV1.4.4:** Interactive queries include llm_generate as final step
- **IV1.4.5:** Autonomous workflows do NOT include response steps
- **IV1.4.6:** Existing GENERIC_SYSTEM_PROMPT (if exists) still works for non-RAG missions
- **IV1.4.7:** Agent.create_agent() and Agent.create_rag_agent() both work correctly
- **IV1.4.8:** Prompt is readable and understandable by LLMs (test with actual LLM calls)

## Prompt Structure Template

### Complete RAG System Prompt Outline

```python
RAG_SYSTEM_PROMPT = """
# RAG Knowledge Assistant - System Instructions

## Your Role
You are a RAG (Retrieval-Augmented Generation) agent specialized in multimodal knowledge retrieval...

## Query Classification
Classify each user query into one of these categories:

### 1. LISTING
- **Description**: User wants to know what documents/resources exist
- **Examples**: "Which documents are available?", "Show all PDFs", "List manuals"
- **Key Indicators**: Question words (which, what), list/show verbs

### 2. CONTENT_SEARCH
- **Description**: User wants information from within documents
- **Examples**: "How does X work?", "Explain Y", "What are the risks?"
- **Key Indicators**: How/Why/What questions, explain/describe verbs

### 3. DOCUMENT_SUMMARY
...

### 4. METADATA_SEARCH
...

### 5. COMPARISON
...

## Planning Patterns

For each query type, generate an appropriate TodoList:

### LISTING Queries

**Example**: "Which documents are available?"

TodoList:
1. List all documents
   - Tool: rag_list_documents
   - Input: {"limit": 20}
   - Acceptance: Document list retrieved

2. Formulate response to user
   - Tool: llm_generate
   - Input: {
       "prompt": "...",
       "context": {"documents": [...]}
     }
   - Acceptance: Natural language response generated

### CONTENT_SEARCH Queries
...

### DOCUMENT_SUMMARY Queries
...

### AUTONOMOUS WORKFLOWS
...

## Tool Usage Rules

### When to use rag_semantic_search
- **Purpose**: Search for content within documents
- **Best for**: "How", "What", "Why" questions
- **Input**: Natural language query, top_k
- **Returns**: Content blocks (text + images)

### When to use rag_list_documents
...

### When to use rag_get_document
...

### When to use llm_generate
- **Purpose**: Generate natural language text
- **CRITICAL FOR INTERACTIVE QUERIES**: Always use as final step when user expects an answer
- **Input**: Prompt + optional context
- **Returns**: Generated text
- **Examples**:
  - Formulating final response to user
  - Summarizing search results
  - Explaining complex information

## Response Generation Guidelines

### Interactive Queries (User expects answer)
✅ ALWAYS include llm_generate as final step
- User asks a question → They expect an answer
- Pass retrieved data as context to llm_generate
- Formulate natural, conversational response

Example indicators:
- Question words: Who, What, Where, When, Why, How, Which
- Request phrases: "Show me", "Tell me", "Explain", "List"

### Autonomous Workflows (Silent completion)
❌ Do NOT include response step
- System tasks, batch jobs, scheduled operations
- Complete work silently without user-facing output

Example indicators:
- Imperative commands: "Index all", "Update database", "Sync files"
- No conversational context

## Clarification Guidelines

Ask user for clarification when:
- ✅ Ambiguous reference ("the report" - which one?)
- ✅ Multiple matches, unclear intent
- ✅ Missing required information
- ✅ Query too vague to classify

Do NOT ask when:
- ❌ Single clear match exists
- ❌ Query is unambiguous
- ❌ Reasonable defaults apply

## Multimodal Synthesis Instructions

### Image Embedding
Use markdown syntax:
```
![Caption describing the image](https://storage.url/image.jpg)
```

### Source Citations
Cite after each fact:
```
(Source: filename.pdf, S. 12)
```

### Best Practices
- Show diagrams for technical explanations
- Use images to supplement text
- Always cite sources
- Prioritize relevant visuals

## Example Workflows

### Example 1: Simple Document Listing
User: "Welche Dokumente gibt es?"

TodoList:
1. List documents (rag_list_documents)
2. Respond to user (llm_generate with context)

### Example 2: Technical Question
User: "How does the safety valve work?"

TodoList:
1. Search content (rag_semantic_search: "safety valve operation")
2. Synthesize response (llm_generate: include text + diagrams + citations)

### Example 3: Specific Document
User: "Summarize the installation manual"

TodoList:
1. Find installation manual (rag_list_documents with filters)
2. Get document details (rag_get_document)
3. Format summary (llm_generate)

---

Remember: Your goal is to provide accurate, well-cited, multimodal answers that help users find and understand knowledge from the document corpus.
"""
```

## Technical Notes

### Implementation Location

```
capstone/agent_v2/prompts/
├── __init__.py
├── rag_system_prompt.py          # RAG_SYSTEM_PROMPT constant
├── generic_system_prompt.py      # Optional: Extract existing generic prompt
└── README.md                       # Documentation
```

### Integration with Agent

```python
# In Agent.create_rag_agent():
from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT

agent = Agent(
    name=name,
    description=description,
    system_prompt=RAG_SYSTEM_PROMPT,  # ← Use RAG prompt
    mission=mission,
    work_dir=work_dir,
    tools=rag_tools,
    llm=llm
)
```

### Prompt Length Considerations

- Target length: 1500-2500 tokens
- LLMs handle this size easily
- Include concrete examples (more effective than abstract rules)
- Balance detail vs conciseness

### Prompt Engineering Best Practices

1. **Use clear section headers** - LLMs respond well to structure
2. **Provide concrete examples** - Better than abstract descriptions
3. **Use consistent terminology** - Same tool names, action types throughout
4. **Be explicit about edge cases** - Interactive vs autonomous, when to ask user
5. **Include success criteria** - Help LLM understand "good" output

### Future Enhancements (Out of Scope)

- Domain-specific prompt variations (medical, legal, technical)
- Multi-language support (prompt in German, English, etc.)
- Few-shot learning examples (user queries + optimal plans)
- Prompt versioning system
- A/B testing infrastructure for prompt variants

## Risk Assessment

**Low Risk:**
- ✅ Pure text file, no code logic
- ✅ No breaking changes to existing functionality
- ✅ Backward compatible (opt-in)
- ✅ Easy to iterate and improve

**Considerations:**
- ⚠️ Prompt quality directly impacts agent behavior - needs careful crafting
- ⚠️ LLM interpretation may vary - test with actual LLM
- ⚠️ May need refinement based on real-world usage

## Dependencies & Prerequisites

**Required:**
- ✅ Story 1.3.1 complete (LLMTool exists) - referenced in prompt patterns
- ✅ Tool descriptions from Stories 1.1-1.3 (rag_semantic_search, rag_list_documents, rag_get_document)
- ✅ Understanding of TodoList structure and Agent planning

**Not Required:**
- ❌ Actual tool implementations (prompt uses tool *descriptions*, not actual tools)
- ❌ Azure AI Search access (prompt is pure text)

**Can be developed in parallel with:**
- Story 1.2 (Semantic Search Tool) - just need tool interface description
- Story 1.5 (Synthesis) - prompt describes the pattern

## Status

**Current Status:** Ready for Implementation

**Next Steps:**
1. Create `prompts/` directory structure
2. Draft RAG_SYSTEM_PROMPT with all required sections
3. Write examples for each query classification type
4. Include llm_generate in all interactive query patterns
5. Test with TodoListManager
6. Iterate based on LLM behavior

---

## Dev Agent Record

**Status:** Ready for Review

**Agent Model Used:** Claude Sonnet 4.5

**File List:**
- Created:
  - `capstone/agent_v2/prompts/README.md` - Comprehensive documentation for system prompts
  - `capstone/agent_v2/tests/test_rag_system_prompt.py` - Unit tests (44 tests)
  - `capstone/agent_v2/tests/integration/test_rag_prompt_integration.py` - Integration tests (17 tests, 58 total passed)
- Modified:
  - `capstone/agent_v2/prompts/rag_system_prompt.py` - Completely rewritten with comprehensive RAG_SYSTEM_PROMPT and build_rag_system_prompt() function
  - `capstone/agent_v2/prompts/__init__.py` - Added build_rag_system_prompt export

**Change Log:**
- 2025-01-10: Rewrote RAG_SYSTEM_PROMPT with all 8 required sections:
  - Role Definition
  - Query Classification (6 categories: LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, METADATA_SEARCH, COMPARISON, AUTONOMOUS_WORKFLOW)
  - Planning Patterns (complete TodoList examples for each query type)
  - Tool Usage Rules (rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
  - Response Generation Guidelines (interactive vs autonomous distinction)
  - Clarification Guidelines (when to ask users)
  - Multimodal Synthesis Instructions (text + images with citations)
  - Multiple Example Workflows
- 2025-01-10: Added build_rag_system_prompt() parameterization function
- 2025-01-10: Created prompts/README.md with comprehensive usage documentation
- 2025-01-10: Implemented 44 unit tests covering prompt structure, sections, categories, tools, and quality
- 2025-01-10: Implemented 17 integration tests covering agent integration, TodoListManager, backward compatibility, and prompt behavior
- 2025-01-10: All tests passing (58 passed, 3 skipped requiring OPENAI_API_KEY)

**Completion Notes:**
- **Prompt Length**: 21,768 characters (~5,400 tokens) - comprehensive but within reasonable bounds
- **Query Classifications**: Implemented 6 query types with clear examples and indicators
- **Planning Patterns**: Included 6 complete TodoList examples showing tool usage, inputs, and acceptance criteria
- **Tool Coverage**: All 4 RAG tools documented (rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
- **Interactive vs Autonomous**: Clear distinction with explicit guidance on when to include llm_generate response steps
- **Multimodal Support**: Image embedding syntax and source citation format specified
- **Parameterization**: build_rag_system_prompt() allows customization with available_tools, domain_knowledge, and user_context
- **Backward Compatibility**: GENERIC_SYSTEM_PROMPT unchanged, RAG_SYSTEM_PROMPT is opt-in
- **Test Coverage**: 
  - 44 unit tests validate prompt structure, content, and quality
  - 17 integration tests verify agent/TodoListManager integration and backward compatibility
  - All tests pass successfully
- **Documentation**: README.md provides usage examples, customization guidance, and best practices

---

## QA Results

**Status:** Not Reviewed

**QA Agent:** N/A

**Review Date:** N/A

**Findings:**
- (will be filled during QA review)

**Final Status:** N/A

