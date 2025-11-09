# 7. Appendices

### 7.1 Azure AI Search Index Schemas

#### Content Blocks Index (`content-blocks`)

| Field | Type | Description |
|-------|------|-------------|
| block_id | String (key) | Unique identifier |
| doc_id | String | Parent document reference |
| page_number | Int | Source page |
| block_type | String | "text" or "image" |
| content | String | Text content (if text block) |
| content_vector | Collection(Single) | Embedding for text |
| image_url | String | Blob Storage URL (if image block) |
| image_caption | String | AI-generated caption (if image) |
| image_caption_vector | Collection(Single) | Embedding for caption |
| access_control_list | Collection(String) | Security: user_ids, departments |

#### Documents Metadata Index (`documents-metadata`)

| Field | Type | Description |
|-------|------|-------------|
| doc_id | String (key) | Unique identifier |
| filename | String | Original filename |
| title | String | Extracted title |
| document_type | String | "Manual", "Report", etc. |
| upload_date | DateTimeOffset | Upload timestamp |
| author | String | Document author |
| department | String | Owning department |
| page_count | Int | Number of pages |
| summary_brief | String | Short summary (2-3 sentences) |
| summary_standard | String | Full summary (1-2 paragraphs) |
| access_control_list | Collection(String) | Security: user_ids, departments |

### 7.2 Environment Variable Template

```bash
# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=https://ms-ai-search-dev-01.search.windows.net
AZURE_SEARCH_API_KEY=<your-api-key>

# Index Names (optional, defaults provided)
AZURE_SEARCH_DOCUMENTS_INDEX=documents-metadata
AZURE_SEARCH_CONTENT_INDEX=content-blocks

# User Context (example for testing)
RAG_USER_ID=user123
RAG_DEPARTMENT=engineering
RAG_ORG_ID=org456
```

### 7.3 Glossary

- **RAG**: Retrieval-Augmented Generation - AI pattern combining search with LLM generation
- **Content Block**: A single unit of content (text chunk or image) in the search index
- **Multimodal**: Supporting both text and images
- **Semantic Search**: Search based on meaning rather than exact keyword matching
- **OData Filter**: Query syntax for filtering Azure Search results
- **SAS URL**: Shared Access Signature URL for secure Azure Blob access
- **ReAct**: Reasoning + Acting agent pattern (Thought → Action → Observation)
- **TodoList**: The agent's deterministic execution plan
- **Acceptance Criteria**: Observable conditions that define when a TodoItem is complete

---

**End of PRD**

*Generated with assistance from Claude Code*
*Co-Authored-By: Claude <noreply@anthropic.com>*
