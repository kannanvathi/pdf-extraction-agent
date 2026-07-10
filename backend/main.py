"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config import get_settings
from backend.db.repository import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect MongoDB and cache repo on app state
    try:
        app.state.repo = await connect_db()
        app.state.db_status = "connected"
    except Exception as exc:  # pragma: no cover - defensive for deployment
        app.state.repo = None
        app.state.db_status = "disconnected"
        app.state.db_error = str(exc)
    yield
    # Shutdown: close MongoDB client
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Loss Run Extraction Agent API",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "database": getattr(app.state, "db_status", "unknown"),
        }

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
