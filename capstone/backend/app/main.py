from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.conversation import router as conversation_router
from app.api.agent import router as agent_router
from app.api.rag import router as rag_router


def create_app() -> FastAPI:
	app = FastAPI(title="IDP Copilot Backend", version="0.1.0")

	@app.get("/healthz")
	async def healthz() -> dict:
		return {"status": "ok"}

	app.include_router(chat_router, prefix="/api")
	app.include_router(conversation_router, prefix="/api")
	app.include_router(agent_router, prefix="/api")
	app.include_router(rag_router, prefix="/api")
	return app


app = create_app()


