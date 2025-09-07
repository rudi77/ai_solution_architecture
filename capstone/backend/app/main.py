from __future__ import annotations

from fastapi import FastAPI
from .api.tools import router as tools_router
from .api.agent_systems import router as agent_systems_router
from .api.sessions import router as sessions_router
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Orchestration API", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(tools_router)
    app.include_router(agent_systems_router)
    app.include_router(sessions_router)

    return app


app = create_app()


