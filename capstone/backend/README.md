# IDP Copilot Backend

FastAPI backend for the IDP Copilot capstone.

## Run (with uv)

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: `http://localhost:8000/docs`

## RAG with ChromaDB (optional)

Set environment variables (e.g., via `.env` or shell) to enable embeddings-backed RAG:

```powershell
$env:OPENAI_API_KEY = "<your-key>"
$env:CHROMA_DB_DIR = ".\chroma"
$env:DOCUMENTS_ROOT = "..\documents"
```

Endpoints:
- `POST /api/rag/reindex` to index documents from `DOCUMENTS_ROOT`
- `POST /api/rag/query` to query

If `OPENAI_API_KEY` is not set, the service falls back to simple full-text search over markdown and text files.