from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


class Settings:
	"""Application settings loaded from environment variables.

	Attributes
	----------
	openai_api_key: Optional[str]
		API key used for OpenAI embeddings. If missing, RAG falls back to simple search.
	openai_embeddings_model: str
		The embeddings model name to use.
	chroma_persist_dir: str
		Directory where ChromaDB should persist its data.
	documents_root: str
		Root directory containing source documents to index.
	"""

	def __init__(self) -> None:
		self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
		self.openai_embeddings_model: str = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
		self.chroma_persist_dir: str = os.getenv("CHROMA_DB_DIR", str(Path.cwd().joinpath("chroma")))
		self.documents_root: str = os.getenv("DOCUMENTS_ROOT", str(Path.cwd().joinpath("documents")))
		self.agent_engine: str = os.getenv("AGENT_ENGINE", "auto")  # auto | builtin | adk
		# SQLite database path for persistence (conversations, runs, tasks, events)
		self.sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", str(Path.cwd().joinpath("data", "app.db")))

		# MCP integration (optional)
		# Enable by setting MCP_ENABLE=true and optionally configuring one or more servers.
		self.mcp_enable: bool = os.getenv("MCP_ENABLE", "false").lower() in {"1", "true", "yes", "on"}
		# Convenience: filesystem MCP server root. If set, will attempt to launch via npx stdio.
		self.mcp_filesystem_dir: Optional[str] = os.getenv("MCP_FILESYSTEM_DIR")
		# Generic stdio server specs as JSON array: [{"command":"npx","args":["pkg", "--flag"]}, ...]
		self.mcp_stdio_json: Optional[str] = os.getenv("MCP_STDIO_JSON")


settings = Settings()


