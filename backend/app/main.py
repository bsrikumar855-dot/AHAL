"""FastAPI app factory.

Registers the v1 API router and translates domain exceptions
(core/exceptions.py) into HTTP responses, so route handlers and everything
they call never import fastapi themselves.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_v1_router
from backend.app.core.exceptions import IndexJobNotFoundError, RepoNotFoundError


def create_app() -> FastAPI:
    app = FastAPI(
        title="AHAL AI Backend",
        summary="PR blast-radius prediction — Increment 1: repository connection + indexing.",
    )
    app.include_router(api_v1_router)

    @app.exception_handler(RepoNotFoundError)
    async def handle_repo_not_found(request: Request, exc: RepoNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(IndexJobNotFoundError)
    async def handle_index_job_not_found(
        request: Request, exc: IndexJobNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
