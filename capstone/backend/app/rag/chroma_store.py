from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Tuple

from app.settings import settings


def is_enabled() -> bool:
	"""Return True if Chroma-backed RAG with embeddings is configured."""
	return bool(settings.openai_api_key)


def _hash_text(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _list_source_files(root: str) -> List[Path]:
	base = Path(root)
	if not base.exists():
		return []
	return [p for p in base.glob("**/*") if p.is_file() and p.suffix in {".md", ".txt"}]


def _ensure_collection():
	"""Create or load a Chroma collection with OpenAI embeddings."""
	import chromadb
	from chromadb.utils import embedding_functions

	client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
	emb_fn = embedding_functions.OpenAIEmbeddingFunction(
		api_key=settings.openai_api_key,
		model_name=settings.openai_embeddings_model,
	)
	collection = client.get_or_create_collection(name="documents", embedding_function=emb_fn)
	return collection


def _read_file_safely(path: Path) -> str:
	try:
		return path.read_text(encoding="utf-8", errors="ignore")
	except Exception:
		return ""


def _chunk_text(text: str, max_tokens: int = 500, overlap: int = 100) -> List[str]:
	"""Simple character-based chunking as a stand-in for token-based splitting."""
	if not text:
		return []
	chunks: List[str] = []
	start = 0
	length = max_tokens
	while start < len(text):
		end = min(len(text), start + length)
		chunks.append(text[start:end])
		if end == len(text):
			break
		start = max(0, end - overlap)
	return chunks


def reindex_documents() -> int:
	"""Rebuild the Chroma collection from files under documents_root.

	Returns the number of chunks upserted.
	"""
	collection = _ensure_collection()
	paths = _list_source_files(settings.documents_root)
	total_chunks = 0
	batch_size = 50  # Process documents in smaller batches
	
	ids: List[str] = []
	docs: List[str] = []
	metas: List[dict] = []
	
	for path in paths:
		text = _read_file_safely(path)
		for idx, chunk in enumerate(_chunk_text(text)):
			id = f"{path}::{idx}::{_hash_text(chunk)[:16]}"
			ids.append(id)
			docs.append(chunk)
			metas.append({"path": str(path), "chunk": idx})
			
			# Process in batches to avoid token limits
			if len(ids) >= batch_size:
				collection.upsert(ids=ids, documents=docs, metadatas=metas)
				total_chunks += len(ids)
				ids, docs, metas = [], [], []
	
	# Process remaining items
	if ids:
		collection.upsert(ids=ids, documents=docs, metadatas=metas)
		total_chunks += len(ids)
	
	return total_chunks


def query(query: str, max_results: int = 5) -> List[Tuple[str, str]]:
	"""Query the Chroma collection and return list of (path, snippet)."""
	collection = _ensure_collection()
	res = collection.query(query_texts=[query], n_results=max_results)
	paths: List[str] = []
	snippets: List[str] = []
	if res and res.get("metadatas") and res.get("documents"):
		metas = res["metadatas"][0]
		docs = res["documents"][0]
		for meta, doc in zip(metas, docs):
			paths.append(str(meta.get("path", "")))
			snippets.append(doc[:300])
	return list(zip(paths, snippets))


