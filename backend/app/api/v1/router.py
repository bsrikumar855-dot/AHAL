"""Aggregates all v1 routers. Add new resource routers here as they're built."""
from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1 import repos

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(repos.router)
