from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple


def list_documents(root: str) -> List[Path]:
	base = Path(root)
	if not base.exists():
		return []
	return [p for p in base.glob("**/*") if p.is_file() and p.suffix in {".md", ".txt"}]


def search_documents(root: str, query: str, max_results: int = 5) -> List[Tuple[str, str]]:
	query_lower = query.lower()
	results: List[Tuple[str, str]] = []
	for path in list_documents(root):
		try:
			text = path.read_text(encoding="utf-8", errors="ignore")
		except Exception:
			continue
		if query_lower in text.lower():
			snippet = _extract_snippet(text, query_lower)
			results.append((str(path), snippet))
			if len(results) >= max_results:
				break
	return results


def _extract_snippet(text: str, query_lower: str, window: int = 200) -> str:
	idx = text.lower().find(query_lower)
	if idx == -1:
		return text[:window]
	start = max(0, idx - window // 2)
	end = min(len(text), idx + len(query_lower) + window // 2)
	return text[start:end]


