# Story 1.2.1: Early RAG Agent Integration & CLI Testing

**Epic:** Multimodal RAG Knowledge Retrieval for Agent Framework
**Story ID:** RAG-1.2.1
**Priority:** High (Integration Validation)
**Estimate:** 4-6 hours
**Status:** Ready for Review
**Depends on:** Story 1.2 (Semantic Search Tool)

---

## User Story

**As a** developer building the RAG enhancement,
**I want** to create a working RAG agent with the SemanticSearchTool and test it via CLI,
**so that** I can validate the integration pattern works before building additional tools (Stories 1.3-1.5).

---

## Story Context

### Purpose

This is an **early integration story** inserted after Story 1.2 to:
1. **Validate** that SemanticSearchTool works with the Agent class
2. **Create** a minimal RAG system prompt for initial testing
3. **Provide** a CLI command for manual testing and demonstrations
4. **De-risk** Stories 1.3-1.5 by proving the integration pattern works

### Why Now?

Story 1.2 implemented an excellent SemanticSearchTool, but it hasn't been tested with the actual Agent yet. Before building 3 more tools (Stories 1.3-1.5), we need to:
- Prove the tool registration pattern works
- Test the Agent can actually use the tool correctly
- Get early feedback on system prompt effectiveness
- Create a CLI command for stakeholder demos

### Integration with Existing System

- **Builds on:** Story 1.1 (AzureSearchBase), Story 1.2 (SemanticSearchTool)
- **Creates:** Minimal `Agent.create_rag_agent()` factory, basic RAG prompt, CLI command
- **Validates:** End-to-end flow: CLI → Agent → Tool → Azure Search

---

## Acceptance Criteria

### AC1.2.1.1: Basic RAG System Prompt

**File:** `capstone/agent_v2/prompts/rag_system_prompt.py` (**NEW**)

**Requirements:**
- [ ] Create `prompts/` directory structure:
  ```
  agent_v2/prompts/
  ├── __init__.py
  ├── generic_system_prompt.py  (move existing GENERIC_SYSTEM_PROMPT here)
  └── rag_system_prompt.py      (new)
  ```

- [ ] `rag_system_prompt.py` contains `RAG_SYSTEM_PROMPT` string with:
  - Tool description: "You have access to `rag_semantic_search` tool for searching enterprise documents"
  - Basic usage instruction: "When user asks about documents/information, use rag_semantic_search with natural language query"
  - Response format: "Always cite sources using (Source: filename.pdf, p.X)"
  - Simplified query classification (just CONTENT_SEARCH for now)

**Example Prompt (Minimal Version):**
```python
RAG_SYSTEM_PROMPT = """
You are a RAG-enabled knowledge assistant with access to enterprise documents via Azure AI Search.

AVAILABLE TOOLS:
- rag_semantic_search(query: str, top_k: int = 10): Search across text and image content blocks

WHEN TO USE RAG_SEMANTIC_SEARCH:
- User asks about information in documents
- User asks "what does X say about Y?"
- User requests specific content from files

RESPONSE FORMAT:
- Include relevant quotes from retrieved text
- Embed images using markdown: ![caption](image_url)
- Always cite sources: (Source: filename.pdf, p.5)
- If no relevant content found, say so clearly

EXAMPLE WORKFLOW:
User: "What does the manual say about pump maintenance?"
You: Use rag_semantic_search with query="pump maintenance manual"
Then synthesize results into answer with citations.
"""
```

---

### AC1.2.1.2: RAG Agent Factory Method

**File:** `capstone/agent_v2/agent.py` (**MODIFIED**)

**Requirements:**
- [ ] Add static method `Agent.create_rag_agent(session_id: str, user_context: Dict = None) -> Agent`:
  ```python
  @staticmethod
  async def create_rag_agent(
      session_id: str,
      user_context: Optional[Dict[str, Any]] = None
  ) -> "Agent":
      """
      Create an agent with RAG capabilities.

      Args:
          session_id: Unique session identifier
          user_context: User context for security filtering (user_id, org_id, scope)

      Returns:
          Agent instance with RAG tools and system prompt
      """
      from capstone.agent_v2.tools.rag_semantic_search_tool import SemanticSearchTool
      from capstone.agent_v2.prompts.rag_system_prompt import RAG_SYSTEM_PROMPT

      # Create RAG tools
      rag_tools = [
          SemanticSearchTool(user_context=user_context)
      ]

      # Create agent with RAG prompt
      agent = Agent(
          session_id=session_id,
          tools=rag_tools,
          system_prompt=RAG_SYSTEM_PROMPT  # Override generic prompt
      )

      return agent
  ```

- [ ] Verify `Agent.__init__` accepts `system_prompt` parameter (or add it if missing)
- [ ] Import validation: Ensure imports work correctly

---

### AC1.2.1.3: CLI Command for RAG Testing

**File:** `capstone/agent_v2/cli/commands/rag.py` (**NEW**)

**Requirements:**
- [ ] Create new CLI command file `cli/commands/rag.py`
- [ ] Implement `rag-chat` command that:
  - Loads Azure configuration from environment variables
  - Prompts for user context (user_id, org_id, scope) - optional, defaults to test values
  - Creates RAG agent using `Agent.create_rag_agent()`
  - Starts interactive chat loop
  - Displays agent events (THOUGHT, ACTION, TOOL_RESULT)
  - Handles Ctrl+C gracefully

**Implementation:**
```python
import click
import asyncio
from capstone.agent_v2.agent import Agent

@click.command()
@click.option('--user-id', default='test_user', help='User ID for security filtering')
@click.option('--org-id', default='test_org', help='Organization ID')
@click.option('--scope', default='shared', help='Content scope')
def rag_chat(user_id, org_id, scope):
    """Start interactive RAG chat session."""

    async def run_chat():
        session_id = f"rag_test_{int(time.time())}"
        user_context = {
            "user_id": user_id,
            "org_id": org_id,
            "scope": scope
        }

        agent = await Agent.create_rag_agent(
            session_id=session_id,
            user_context=user_context
        )

        click.echo("RAG Agent started. Type 'exit' to quit.")
        click.echo(f"User context: {user_context}")
        click.echo("-" * 50)

        while True:
            query = click.prompt("\n💬 You", type=str)
            if query.lower() in ['exit', 'quit']:
                break

            async for event in agent.execute(query, session_id):
                if event.type == "THOUGHT":
                    click.echo(f"🤔 Thought: {event.content}")
                elif event.type == "ACTION":
                    click.echo(f"🔧 Action: {event.content}")
                elif event.type == "TOOL_RESULT":
                    click.echo(f"📊 Result: {event.content[:200]}...")
                elif event.type == "COMPLETE":
                    click.echo(f"\n✅ Agent: {event.content}")

    asyncio.run(run_chat())
```

- [ ] Register command in `cli/main.py`:
  ```python
  from capstone.agent_v2.cli.commands import rag
  cli.add_command(rag.rag_chat)
  ```

---

### AC1.2.1.4: Environment Validation

**Requirements:**
- [ ] CLI command validates Azure environment variables before agent creation:
  - `AZURE_SEARCH_ENDPOINT`
  - `AZURE_SEARCH_API_KEY`
  - `AZURE_SEARCH_CONTENT_INDEX` (optional, default: "content-blocks")

- [ ] Clear error message if variables missing:
  ```
  ❌ Azure Search not configured. Please set:
    export AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net
    export AZURE_SEARCH_API_KEY=your-key
  ```

---

### AC1.2.1.5: Basic Integration Test

**File:** `capstone/agent_v2/tests/test_rag_agent_integration.py` (**NEW**)

**Requirements:**
- [ ] Test `Agent.create_rag_agent()` successfully creates agent
- [ ] Test agent has `rag_semantic_search` tool registered
- [ ] Test agent system prompt is RAG_SYSTEM_PROMPT (not generic)
- [ ] Mock test: Agent can execute simple query using mocked SemanticSearchTool

**Example Test:**
```python
@pytest.mark.asyncio
async def test_create_rag_agent():
    """Test RAG agent factory method."""
    agent = await Agent.create_rag_agent(
        session_id="test_rag_001",
        user_context={"user_id": "test_user"}
    )

    # Verify RAG tool registered
    tool_names = [tool.name for tool in agent.tools]
    assert "rag_semantic_search" in tool_names

    # Verify RAG prompt loaded
    assert "rag_semantic_search" in agent.system_prompt.lower()
    assert "enterprise documents" in agent.system_prompt.lower()
```

---

## Definition of Done

- [ ] **Code Complete:**
  - [ ] `prompts/rag_system_prompt.py` created with basic RAG prompt
  - [ ] `Agent.create_rag_agent()` factory method implemented
  - [ ] `cli/commands/rag.py` created with `rag-chat` command
  - [ ] Command registered in CLI main

- [ ] **Tests Pass:**
  - [ ] Integration test for `create_rag_agent()` passes
  - [ ] Manual CLI test: Can start rag-chat and interact with agent
  - [ ] End-to-end test: Query reaches SemanticSearchTool correctly
  - [ ] No regressions in existing agent tests

- [ ] **Validation:**
  - [ ] CLI command starts successfully with valid Azure credentials
  - [ ] Agent can execute rag_semantic_search tool
  - [ ] Results from Azure Search are returned correctly
  - [ ] Agent can synthesize basic response from search results

- [ ] **Documentation:**
  - [ ] README updated with rag-chat command usage
  - [ ] Environment variable setup documented
  - [ ] Example queries provided

---

## Testing Strategy

### Manual Testing Scenario

1. **Setup:**
   ```bash
   export AZURE_SEARCH_ENDPOINT=https://test.search.windows.net
   export AZURE_SEARCH_API_KEY=test-key
   export AZURE_SEARCH_CONTENT_INDEX=content-blocks
   ```

2. **Start CLI:**
   ```bash
   python -m capstone.agent_v2.cli rag-chat --user-id=test_user
   ```

3. **Test Query:**
   ```
   You: What information do you have about pump maintenance?

   Expected:
   🤔 Thought: User is asking about pump maintenance. I should search documents.
   🔧 Action: rag_semantic_search(query="pump maintenance", top_k=5)
   📊 Result: Found 3 content blocks...
   ✅ Agent: Based on the manual (Source: pump_manual.pdf, p.12), ...
   ```

### Unit Test Coverage

- `test_rag_system_prompt_exists()` - Prompt string defined
- `test_create_rag_agent()` - Factory creates agent with RAG tools
- `test_rag_agent_tool_registration()` - Tool properly registered
- `test_rag_agent_system_prompt()` - RAG prompt loaded correctly
- `test_cli_rag_command_exists()` - CLI command registered

---

## Risk Assessment

### Primary Risk: Agent Can't Use Tool Correctly
**Mitigation:**
- Test with mocked tool responses first
- Verify tool schema matches Agent expectations
- Check AgentEvent streaming works correctly

### Rollback Plan
If integration fails:
- Revert agent.py changes (remove create_rag_agent)
- Delete CLI command
- Story 1.2 (tool) remains valid, can retry integration differently

---

## Dependencies

**Depends on:**
- ✅ Story 1.1: Azure Search Base Infrastructure (Done)
- ✅ Story 1.2: Semantic Search Tool (Done)

**Blocks:**
- Story 1.3: Document Metadata Tools (validates pattern for additional tools)
- Story 1.4-1.5: Remaining tools (same integration pattern)
- Story 1.6: Final integration becomes simpler

---

## Success Criteria

**Story is successful when:**
1. ✅ Developer can run `rag-chat` command
2. ✅ Agent successfully calls SemanticSearchTool
3. ✅ Search results returned from Azure Search
4. ✅ Agent synthesizes basic response with source citations
5. ✅ No regressions in existing agent functionality
6. ✅ Integration pattern proven for Stories 1.3-1.5

---

**Estimated Effort:** 4-6 hours
**Complexity:** Medium (new integration, but well-scoped)
**Value:** High (de-risks remaining epic, provides early demo capability)
