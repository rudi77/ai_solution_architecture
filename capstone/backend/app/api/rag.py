from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.rag.simple_store import search_documents


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
	results = search_documents(root="documents", query=payload.query, max_results=payload.max_results)
	return RagQueryResponse(results=[RagDoc(path=p, snippet=s) for p, s in results])


