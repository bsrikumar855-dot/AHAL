"""GitHub Webhook Receiver Endpoint."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.api.v1.deps import get_graph_repository, get_settings_dep
from backend.app.db.session import get_db
from backend.app.graph.graph_repository import GraphRepository
from backend.app.services import github_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def verify_signature(secret: str, signature_header: str, body: bytes) -> bool:
    """Validate webhook HMAC SHA256 signature."""
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    actual = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, actual)


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None, alias="x-github-event"),
    x_hub_signature_256: str | None = Header(None, alias="x-hub-signature-256"),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(get_db),
    graph_repo: GraphRepository = Depends(get_graph_repository),
) -> dict:
    """Receives and processes GitHub pull_request webhook events."""
    body = await request.body()

    # Mandatory signature verification
    if not x_hub_signature_256:
        logger.warning("Missing x-hub-signature-256 header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Hub-Signature-256 header"
        )

    if not verify_signature(settings.github_webhook_secret, x_hub_signature_256, body):
        logger.warning("Webhook signature mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    if x_github_event == "ping":
        return {"status": "ping_ok"}

    if x_github_event != "pull_request":
        return {"status": "ignored_event", "event": x_github_event}

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    action = payload.get("action")
    if action not in ("opened", "synchronize"):
        return {"status": "ignored_action", "action": action}

    # Delegate PR processing
    result = await github_service.handle_pr_event(
        payload=payload,
        session=session,
        graph_repo=graph_repo,
        settings=settings,
    )

    if result is None:
        return {"status": "error_or_skipped"}

    return {"status": "processed", "result": result}
