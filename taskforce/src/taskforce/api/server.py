import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from taskforce.api.routes import execution, health, sessions
from taskforce.infrastructure.tracing import init_tracing, shutdown_tracing

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown events."""
    # Initialize tracing first (before any LLM calls)
    init_tracing()

    await logger.ainfo(
        "fastapi.startup", message="Taskforce API starting..."
    )
    yield
    await logger.ainfo(
        "fastapi.shutdown", message="Taskforce API shutting down..."
    )

    # Shutdown tracing last (flush all pending spans)
    shutdown_tracing()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Taskforce Agent API",
        description=(
            "Production-ready ReAct agent framework "
            "with Clean Architecture"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on environment
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(
        execution.router, prefix="/api/v1", tags=["execution"]
    )
    app.include_router(
        sessions.router, prefix="/api/v1", tags=["sessions"]
    )
    app.include_router(health.router, tags=["health"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8070)
