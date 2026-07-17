"""Integration tests for the GitHub webhook receiver endpoint.

Mocks the GitHub REST API and tests HMAC signature verification, pull_request
opened/synchronize events, and confidence filtering/formatting.
"""
from __future__ import annotations

import hmac
import hashlib
import json
from unittest.mock import patch
import pytest

from backend.app.config import Settings
from backend.app.graph.graph_repository import GraphRepository


def sign_payload(payload: dict, secret: str) -> tuple[bytes, str]:
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, f"sha256={sig}"


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}")


class MockAsyncClient:
    get_json_response = [{"filename": "a.py"}]
    post_called_with = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, **kwargs):
        return MockResponse(self.get_json_response)

    async def post(self, url, **kwargs):
        self.post_called_with.append((url, kwargs.get("json", {})))
        return MockResponse({}, status_code=201)


@pytest.fixture(autouse=True)
def clear_mock_calls():
    MockAsyncClient.post_called_with.clear()


def test_github_webhook_ping_event(api_client, test_settings):
    payload = {"zen": "Keep it logically simple."}
    body_bytes, signature = sign_payload(payload, test_settings.github_webhook_secret)

    resp = api_client.post(
        "/webhooks/github",
        content=body_bytes,
        headers={
            "x-github-event": "ping",
            "x-hub-signature-256": signature,
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ping_ok"


def test_github_webhook_missing_signature(api_client):
    payload = {"action": "opened"}
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    resp = api_client.post(
        "/webhooks/github",
        content=body_bytes,
        headers={
            "x-github-event": "pull_request",
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 400
    assert "Missing X-Hub-Signature-256 header" in resp.json()["detail"]


def test_github_webhook_invalid_signature(api_client, test_settings):
    payload = {"action": "opened"}
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    resp = api_client.post(
        "/webhooks/github",
        content=body_bytes,
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": "sha256=invalid-signature-hash",
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 401
    assert "Invalid signature" in resp.json()["detail"]


def test_github_webhook_ignored_event(api_client, test_settings):
    payload = {"action": "opened"}
    body_bytes, signature = sign_payload(payload, test_settings.github_webhook_secret)

    resp = api_client.post(
        "/webhooks/github",
        content=body_bytes,
        headers={
            "x-github-event": "issues",
            "x-hub-signature-256": signature,
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored_event"


def test_github_webhook_unhandled_action(api_client, test_settings):
    payload = {"action": "closed"}
    body_bytes, signature = sign_payload(payload, test_settings.github_webhook_secret)

    resp = api_client.post(
        "/webhooks/github",
        content=body_bytes,
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": signature,
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored_action"


def test_github_webhook_processed_comment(api_client, fixture_repo, graph_repo: GraphRepository, test_settings):
    # 1. Index the repository so that it is status READY and exists in db
    create_resp = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["repo"]["id"]

    # 2. Save a calibrator for this repo so that predictions have calibrated_score
    fit_pairs = [(0.5, True), (0.5, True), (0.9, True)]
    graph_repo.save_calibrator(repo_id, fit_pairs)

    # Configure min calibrated score setting to ensure our predictions surface
    test_settings.github_comment_min_calibrated_score = 0.4
    test_settings.github_comment_max_predictions = 2

    # 3. Create the webhook payload
    payload = {
        "action": "opened",
        "number": 42,
        "repository": {
            "clone_url": str(fixture_repo),
            "html_url": "https://github.com/test-owner/test-repo",
            "owner": {"login": "test-owner"},
            "name": "test-repo",
        },
        "pull_request": {
            "url": "https://api.github.com/repos/test-owner/test-repo/pulls/42",
            "comments_url": "https://api.github.com/repos/test-owner/test-repo/issues/42/comments",
        }
    }
    body_bytes, signature = sign_payload(payload, test_settings.github_webhook_secret)

    # Patch the AsyncClient and run webhook request
    with patch("backend.app.services.github_service.httpx.AsyncClient", MockAsyncClient):
        resp = api_client.post(
            "/webhooks/github",
            content=body_bytes,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": signature,
                "content-type": "application/json",
            },
        )
        assert resp.status_code == 202
        res_json = resp.json()
        assert res_json["status"] == "processed"
        assert res_json["result"]["commented"] is True

        # Verify MockAsyncClient posted the rendered comment
        assert len(MockAsyncClient.post_called_with) == 1
        comments_url, post_body = MockAsyncClient.post_called_with[0]
        assert comments_url == "https://api.github.com/repos/test-owner/test-repo/issues/42/comments"
        
        comment_md = post_body["body"]
        assert "### 🔍 AHAL PR Blast-Radius Predictions" in comment_md
        assert "Target Component" in comment_md
        assert "Raw Score" in comment_md
        assert "Calibrated Confidence" in comment_md
        assert "`b.py`" in comment_md
        
        # Verify the rendering contains the basis
        assert "structurally reachable" in comment_md or "co-changed" in comment_md
        print(f"\nRendered Comment Example:\n{comment_md.encode('ascii', errors='replace').decode('ascii')}\n")

