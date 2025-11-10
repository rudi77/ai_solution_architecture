# Agent System Prompts

This directory contains system prompts for different agent configurations in the agent_v2 framework.

## Available Prompts

### RAG_SYSTEM_PROMPT

The `RAG_SYSTEM_PROMPT` is a comprehensive system prompt designed for RAG (Retrieval-Augmented Generation) agents that work with multimodal knowledge retrieval from document corpora.

**Location**: `rag_system_prompt.py`

**Purpose**: 
- Teaches the agent to classify different types of knowledge queries (LISTING, CONTENT_SEARCH, DOCUMENT_SUMMARY, etc.)
- Provides clear planning patterns for each query type
- Explains when and how to use RAG tools (rag_semantic_search, rag_list_documents, rag_get_document, llm_generate)
- Defines response generation guidelines for interactive vs autonomous workflows
- Specifies multimodal synthesis instructions (text + images with citations)

**Usage**:

```python
from capstone.agent_v2.prompts import RAG_SYSTEM_PROMPT
from capstone.agent_v2.agent import Agent

# Create a RAG agent with the specialized prompt
rag_agent = Agent(
    name="knowledge_assistant",
    description="Multimodal RAG agent for document retrieval",
    system_prompt=RAG_SYSTEM_PROMPT,
    mission="Answer user questions from enterprise documents",
    tools=[rag_semantic_search, rag_list_documents, rag_get_document, llm_generate],
    work_dir="./rag_work"
)
```

**Key Features**:

1. **Query Classification** - 6 query types:
   - LISTING: Questions about what documents exist
   - CONTENT_SEARCH: Questions about content within documents
   - DOCUMENT_SUMMARY: Requests for document overviews
   - METADATA_SEARCH: Filtering by document properties
   - COMPARISON: Comparing multiple documents
   - AUTONOMOUS_WORKFLOW: System tasks without user interaction

2. **Planning Patterns** - Complete TodoList examples for each query type showing:
   - Tool selection
   - Input parameters
   - Acceptance criteria
   - Whether to include user response step

3. **Tool Usage Rules** - Detailed guidance on:
   - `rag_semantic_search`: Semantic content search
   - `rag_list_documents`: Document listing with filters
   - `rag_get_document`: Detailed document metadata
   - `llm_generate`: Natural language response generation

4. **Response Generation** - Critical distinction between:
   - Interactive queries → Always include `llm_generate` as final step
   - Autonomous workflows → Complete silently without response

5. **Multimodal Synthesis** - Instructions for:
   - Embedding images with markdown syntax
   - Proper source citations
   - Combining text and visual content

## Customization

### Dynamic Prompt Building

Use the `build_rag_system_prompt()` function to customize the prompt with additional context:

```python
from capstone.agent_v2.prompts import build_rag_system_prompt

# Customize with available tools
custom_prompt = build_rag_system_prompt(
    available_tools=["rag_semantic_search", "rag_list_documents"],
    domain_knowledge="This is a medical knowledge base. Use proper medical terminology.",
    user_context="User prefers responses in German."
)

agent = Agent(
    name="medical_rag",
    system_prompt=custom_prompt,
    ...
)
```

**Parameters**:
- `available_tools` (List[str], optional): List of tool names to include in prompt
- `domain_knowledge` (str, optional): Domain-specific guidance (medical, legal, technical standards, etc.)
- `user_context` (str, optional): User/org context (language preferences, permissions, etc.)

## Creating New Prompts

When adding new system prompts:

1. **Create a new file** in this directory (e.g., `my_prompt.py`)
2. **Define the prompt constant**:
   ```python
   MY_SYSTEM_PROMPT = """
   # Your Prompt Title
   
   ## Role
   Define the agent's role...
   
   ## Instructions
   Provide clear instructions...
   """
   ```

3. **Add documentation** - Include docstring explaining purpose and usage

4. **Export from `__init__.py`**:
   ```python
   from capstone.agent_v2.prompts.my_prompt import MY_SYSTEM_PROMPT
   __all__ = [..., "MY_SYSTEM_PROMPT"]
   ```

5. **Optional builder function** - If your prompt needs customization, provide a builder:
   ```python
   def build_my_system_prompt(custom_param: str) -> str:
       """Build customized prompt."""
       return MY_SYSTEM_PROMPT.format(custom_param=custom_param)
   ```

## Prompt Engineering Best Practices

When designing system prompts:

1. **Structure clearly** - Use markdown headers and sections
2. **Provide concrete examples** - More effective than abstract rules
3. **Be explicit about edge cases** - Handle ambiguous situations
4. **Use consistent terminology** - Same terms throughout
5. **Include success criteria** - Help agent understand "good" output
6. **Balance detail vs conciseness** - Aim for 1500-2500 tokens
7. **Test with actual LLMs** - Verify behavior matches intent

## Backward Compatibility

- The generic `GENERIC_SYSTEM_PROMPT` in `agent.py` remains unchanged
- RAG_SYSTEM_PROMPT is opt-in via specialized agent creation
- All existing agent functionality preserved
- Non-RAG agents unaffected by RAG prompt existence

## Testing

System prompts are tested in:
- `tests/test_rag_system_prompt.py` - Unit tests for prompt structure
- `tests/integration/test_rag_prompt_integration.py` - Integration tests with agents

See test files for examples of validating:
- Prompt structure and completeness
- Section presence
- Tool mentions
- Parameterization (if applicable)
- Agent behavior with prompt

## Additional Resources

- **Story 1.4**: RAG System Prompt specification (see `capstone/documents/stories/story-1.4-rag-system-prompt.md`)
- **Agent Documentation**: See `agent.py` for Agent class usage
- **Tool Documentation**: See `tools/` directory for RAG tool implementations

