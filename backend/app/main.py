"""FastAPI app factory.

Registers the v1 API router and translates domain exceptions
(core/exceptions.py) into HTTP responses, so route handlers and everything
they call never import fastapi themselves.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session


from backend.app.api.v1.router import api_v1_router
from backend.app.api.v1.webhooks import router as webhooks_router
from backend.app.core.exceptions import (
    IndexJobNotFoundError,
    RepoIndexingInProgressError,
    RepoNotIndexedError,
    RepoNotFoundError,
)
from backend.app.db.session import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Set up structured logging
    from backend.app.core.logging import setup_logging
    setup_logging()

    yield

    # Shutdown: Gracefully stop background job queues
    from backend.app.api.v1.deps import get_job_queue
    job_queue = get_job_queue()
    if hasattr(job_queue, "shutdown"):
        job_queue.shutdown(wait=True)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AHAL AI Backend",
        summary="PR blast-radius prediction — Increment 1: repository connection + indexing.",
        lifespan=lifespan,
    )
    app.include_router(api_v1_router)
    app.include_router(webhooks_router)

    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")


    @app.exception_handler(RepoNotFoundError)
    async def handle_repo_not_found(request: Request, exc: RepoNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(IndexJobNotFoundError)
    async def handle_index_job_not_found(
        request: Request, exc: IndexJobNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RepoNotIndexedError)
    async def handle_repo_not_indexed(
        request: Request, exc: RepoNotIndexedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RepoIndexingInProgressError)
    async def handle_repo_indexing_in_progress(
        request: Request, exc: RepoIndexingInProgressError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/health", tags=["meta"])
    def health(session: Session = Depends(get_db)) -> dict[str, str]:
        try:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}
        except Exception as exc:
            return {"status": "error", "database": f"disconnected: {exc}"}

    return app


app = create_app()

