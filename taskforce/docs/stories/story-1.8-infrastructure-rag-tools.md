# Story 1.8: Implement Infrastructure - RAG Tools

**Epic**: Build Taskforce Production Framework with Clean Architecture  
**Story ID**: 1.8  
**Status**: Pending  
**Priority**: Medium  
**Estimated Points**: 2  
**Dependencies**: Story 1.2 (Protocol Interfaces)

---

## User Story

As a **developer**,  
I want **RAG tools copied from Agent V2 into infrastructure layer**,  
so that **RAG agent capabilities are available in Taskforce**.

---

## Acceptance Criteria

1. ✅ Create `taskforce/src/taskforce/infrastructure/tools/rag/` directory
2. ✅ Copy RAG tools from `capstone/agent_v2/tools/`:
   - `rag_semantic_search_tool.py` → `semantic_search.py`
   - `rag_list_documents_tool.py` → `list_documents.py`
   - `rag_get_document_tool.py` → `get_document.py`
   - `azure_search_base.py` → `azure_search_base.py` (shared Azure AI Search client)
3. ✅ Each RAG tool implements `ToolProtocol` interface
4. ✅ Preserve all Azure AI Search integration logic (semantic search, document retrieval, security filtering)
5. ✅ Update imports to use taskforce paths
6. ✅ Unit tests with mocked Azure Search client verify query construction
7. ✅ Integration tests with test Azure Search index verify search functionality

---

## Integration Verification

- **IV1: Existing Functionality Verification** - Agent V2 RAG tools continue to function in `capstone/agent_v2/tools/`
- **IV2: Integration Point Verification** - Taskforce RAG tools produce identical search results for identical queries compared to Agent V2 RAG tools
- **IV3: Performance Impact Verification** - Search latency matches Agent V2 (±5%)

---

## Technical Notes

**RAG Tool Migration:**

| Agent V2 Tool | Taskforce Location | Key Features |
|---------------|-------------------|--------------|
| `rag_semantic_search_tool.py` | `rag/semantic_search.py` | Vector search, security filtering |
| `rag_list_documents_tool.py` | `rag/list_documents.py` | Document listing, metadata |
| `rag_get_document_tool.py` | `rag/get_document.py` | Document retrieval by ID |
| `azure_search_base.py` | `rag/azure_search_base.py` | Shared Azure client logic |

**Example RAG Tool:**

```python
# taskforce/src/taskforce/infrastructure/tools/rag/semantic_search.py
from typing import Dict, Any, List
from taskforce.core.interfaces.tools import ToolProtocol
from taskforce.infrastructure.tools.rag.azure_search_base import AzureSearchBase

class SemanticSearchTool(AzureSearchBase):
    """Semantic search in Azure AI Search index.
    
    Implements ToolProtocol for dependency injection.
    """
    
    @property
    def name(self) -> str:
        return "semantic_search"
    
    @property
    def description(self) -> str:
        return "Search documents using semantic vector search"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 5},
                "filters": {"type": "object", "description": "Security filters"}
            },
            "required": ["query"]
        }
    
    async def execute(self, **params) -> Dict[str, Any]:
        """Execute semantic search."""
        # Copy logic from agent_v2/tools/rag_semantic_search_tool.py
        ...
```

**Azure Search Base:**

```python
# taskforce/src/taskforce/infrastructure/tools/rag/azure_search_base.py
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential

class AzureSearchBase:
    """Base class for Azure AI Search tools.
    
    Provides shared client initialization and error handling.
    """
    
    def __init__(
        self,
        endpoint: str,
        index_name: str,
        api_key: str
    ):
        self.endpoint = endpoint
        self.index_name = index_name
        self.client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key)
        )
    
    async def _search(self, query: str, **kwargs) -> List[Dict]:
        """Execute search query."""
        # Copy shared logic from agent_v2/tools/azure_search_base.py
        ...
```

---

## Configuration

RAG tools require Azure AI Search configuration:

```yaml
# taskforce/configs/rag_config.yaml
azure_search:
  endpoint_env: "AZURE_SEARCH_ENDPOINT"
  api_key_env: "AZURE_SEARCH_API_KEY"
  index_name: "documents"
  
security:
  enable_filtering: true
  user_context_fields:
    - "user_id"
    - "org_id"
    - "scope"
```

---

## Testing Strategy

**Unit Tests:**
```python
# tests/unit/infrastructure/tools/rag/test_semantic_search.py
from unittest.mock import AsyncMock, patch
from taskforce.infrastructure.tools.rag.semantic_search import SemanticSearchTool

@pytest.mark.asyncio
async def test_semantic_search_query_construction():
    tool = SemanticSearchTool(
        endpoint="https://test.search.windows.net",
        index_name="test-index",
        api_key="test-key"
    )
    
    with patch.object(tool.client, 'search') as mock_search:
        mock_search.return_value = AsyncMock()
        
        await tool.execute(query="test query", top_k=5)
        
        # Verify search was called with correct params
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[0][0] == "test query"
```

**Integration Tests:**
```python
# tests/integration/test_rag_tools_integration.py
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("AZURE_SEARCH_ENDPOINT"), reason="Azure credentials required")
async def test_semantic_search_with_real_index():
    """Test with actual Azure AI Search index."""
    tool = SemanticSearchTool(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name="test-index",
        api_key=os.getenv("AZURE_SEARCH_API_KEY")
    )
    
    results = await tool.execute(query="machine learning")
    
    assert isinstance(results, dict)
    assert "documents" in results
    assert len(results["documents"]) > 0
```

---

## Definition of Done

- [ ] All RAG tools copied to `infrastructure/tools/rag/`
- [ ] Each tool implements ToolProtocol
- [ ] Azure Search client logic preserved in shared base class
- [ ] Imports updated to taskforce paths
- [ ] Unit tests with mocked Azure client (≥80% coverage)
- [ ] Integration tests with test Azure Search index
- [ ] Search results match Agent V2 for identical queries
- [ ] Performance matches Agent V2 (±5%)
- [ ] Code review completed
- [ ] Code committed to version control

