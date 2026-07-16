"""End-to-end API test: POST /repos -> GET status -> READY with a real graph
summary. Uses the SynchronousJobQueue test double (conftest.py) so indexing
completes deterministically instead of racing a background thread.
"""
from __future__ import annotations


def test_connect_repo_indexes_and_reports_ready(api_client, fixture_repo):
    create_resp = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})
    assert create_resp.status_code == 201
    body = create_resp.json()
    repo_id = body["repo"]["id"]
    job_id = body["job"]["id"]
    assert body["repo"]["url"] == str(fixture_repo)

    get_resp = api_client.get(f"/api/v1/repos/{repo_id}")
    assert get_resp.status_code == 200
    repo_data = get_resp.json()
    assert repo_data["status"] == "ready"
    assert repo_data["node_count"] == 2
    assert repo_data["edge_count"] == 1
    assert repo_data["commit_count"] == 2

    job_resp = api_client.get(f"/api/v1/repos/{repo_id}/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"


def test_get_unknown_repo_returns_404(api_client):
    resp = api_client.get("/api/v1/repos/does-not-exist")
    assert resp.status_code == 404


def test_get_unknown_job_returns_404(api_client, fixture_repo):
    create_resp = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})
    repo_id = create_resp.json()["repo"]["id"]

    resp = api_client.get(f"/api/v1/repos/{repo_id}/jobs/does-not-exist")
    assert resp.status_code == 404


def test_job_from_a_different_repo_returns_404(api_client, fixture_repo):
    first = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)}).json()
    second = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)}).json()

    resp = api_client.get(f"/api/v1/repos/{first['repo']['id']}/jobs/{second['job']['id']}")
    assert resp.status_code == 404


def test_list_repos_returns_connected_repos(api_client, fixture_repo):
    api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})

    resp = api_client.get("/api/v1/repos")

    assert resp.status_code == 200
    assert len(resp.json()) == 1
