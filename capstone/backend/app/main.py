from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.chat_v2 import router as chat_v2_router
from app.api.conversation import router as conversation_router
from app.api.agent import router as agent_router
from app.api.rag import router as rag_router
from app.settings import settings
from app.persistence.sqlite import init_db


def create_app() -> FastAPI:
	app = FastAPI(title="IDP Copilot Backend", version="0.1.0")

	# Add CORS middleware
	app.add_middleware(
		CORSMiddleware,
		allow_origins=["*"],  # Allow all origins for development
		allow_credentials=True,
		allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
		allow_headers=["*"],
	)

	@app.get("/healthz")
	async def healthz() -> dict:
		return {"status": "ok"}

	app.include_router(chat_router, prefix="/api")
	app.include_router(chat_v2_router, prefix="/api")
	app.include_router(conversation_router, prefix="/api")
	app.include_router(agent_router, prefix="/api")
	app.include_router(rag_router, prefix="/api")

	# Initialize database after routers are mounted
	init_db(settings.sqlite_db_path)
	return app


app = create_app()


