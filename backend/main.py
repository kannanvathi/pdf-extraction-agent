"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config import get_settings
from backend.db.repository import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect MongoDB and cache repo on app state
    app.state.repo = await connect_db()
    yield
    # Shutdown: close MongoDB client
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PDF Extraction Agent API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
