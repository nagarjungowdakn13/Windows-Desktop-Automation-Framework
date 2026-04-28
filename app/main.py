"""FastAPI application entry point.

Starts the background worker via the lifespan context, mounts the API router,
and ensures the database schema is created.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.core.logger import get_logger
from app.db.database import init_db
from app.workers.background import BackgroundWorker

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring the DB schema up and run a single background worker for the app's lifetime."""
    init_db()
    worker = BackgroundWorker()
    await worker.start()
    app.state.worker = worker
    logger.info("application started")
    try:
        yield
    finally:
        await worker.stop()
        logger.info("application stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Windows Desktop Automation Framework",
        version=__version__,
        description="JSON-driven desktop automation pipelines with retries, logging, and a REST API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
