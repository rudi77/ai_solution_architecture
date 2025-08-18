from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.rag.simple_store import search_documents
from app.rag import chroma_store
from app.settings import settings


router = APIRouter(prefix="/rag", tags=["rag"])


class RagQueryRequest(BaseModel):
	query: str = Field(min_length=2)
	max_results: int = 5


class RagDoc(BaseModel):
	path: str
	snippet: str


class RagQueryResponse(BaseModel):
	results: List[RagDoc]


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(payload: RagQueryRequest) -> RagQueryResponse:
	if chroma_store.is_enabled():
		results = chroma_store.query(payload.query, max_results=payload.max_results)
	else:
		results = search_documents(root=settings.documents_root, query=payload.query, max_results=payload.max_results)
	return RagQueryResponse(results=[RagDoc(path=p, snippet=s) for p, s in results])


@router.post("/reindex")
async def rag_reindex() -> dict:
	if not chroma_store.is_enabled():
		return {"status": "skipped", "reason": "embeddings not configured"}
	count = chroma_store.reindex_documents()
	return {"status": "ok", "chunks": count}


