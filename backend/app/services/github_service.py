"""Orchestrates processing of GitHub PR events: match repository URL, fetch PR files, run prediction, render and post comments."""
from __future__ import annotations

import logging
import httpx
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.models import RepoStatus
from backend.app.graph.graph_repository import GraphRepository
from backend.app.repositories.repo_repository import RepoRepository
from backend.app.services.prediction_service import get_predictions

logger = logging.getLogger(__name__)


async def handle_pr_event(
    payload: dict,
    session: Session,
    graph_repo: GraphRepository,
    settings: Settings,
) -> dict | None:
    """Processes a PR event payload by fetching changed files, predicting blast radius, and posting a comment."""
    repo_data = payload.get("repository", {})
    clone_url = repo_data.get("clone_url")
    html_url = repo_data.get("html_url")
    pull_request = payload.get("pull_request", {})
    pr_number = payload.get("number")

    if not (clone_url or html_url) or not pr_number:
        logger.warning("Missing clone_url/html_url or pull_request number in payload")
        return None

    # Find the repository in our database matching the clone_url or html_url
    repos = RepoRepository(session).list_all()
    matched_repo = None
    for r in repos:
        if (clone_url and _urls_match(r.url, clone_url)) or (html_url and _urls_match(r.url, html_url)):
            matched_repo = r
            break

    if not matched_repo:
        logger.warning(f"No matching repo found in database for clone_url={clone_url} or html_url={html_url}")
        return None

    if matched_repo.status != RepoStatus.READY:
        logger.warning(f"Matched repo {matched_repo.id} status is {matched_repo.status}, skipping prediction.")
        return None

    # Retrieve changed files in the PR
    files_url = pull_request.get("url")
    if files_url:
        files_url = files_url + "/files"
    else:
        owner = repo_data.get("owner", {}).get("login")
        repo_name = repo_data.get("name")
        files_url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/files"

    headers = {
        "User-Agent": "AHAL-Predictor",
        "Accept": "application/vnd.github.v3+json",
    }
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(files_url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            files_data = resp.json()
        except Exception as exc:
            logger.error(f"Failed to fetch files for PR {pr_number} from GitHub: {exc}")
            return None

    changed_files = [f.get("filename") for f in files_data if f.get("filename")]
    if not changed_files:
        logger.info(f"No changed files found for PR {pr_number}, skipping prediction.")
        return None

    # Run predictions
    try:
        preds = get_predictions(
            repo_id=matched_repo.id,
            changed_files=changed_files,
            session=session,
            graph_repo=graph_repo,
        )
    except Exception as exc:
        logger.error(f"Failed to compute predictions for repo {matched_repo.id}: {exc}")
        return None

    # Filter and rank predictions
    # Filter predictions above settings.github_comment_min_calibrated_score.
    # Note: "Default to under-surfacing" - so if calibrated_score is None, we filter it out.
    surfaced_preds = []
    for p in preds:
        calibrated_score = p.get("calibrated_score")
        if calibrated_score is not None and calibrated_score >= settings.github_comment_min_calibrated_score:
            surfaced_preds.append(p)

    # Sort descending by calibrated score
    surfaced_preds.sort(key=lambda x: x["calibrated_score"], reverse=True)
    # Cap predictions shown
    surfaced_preds = surfaced_preds[:settings.github_comment_max_predictions]

    if not surfaced_preds:
        logger.info("No predictions met the minimum calibrated confidence threshold.")
        return {"commented": False, "reason": "No predictions above threshold"}

    # Formulate PR comment body
    comment_body = render_pr_comment(surfaced_preds)

    # Post comment back to PR
    comments_url = pull_request.get("comments_url")
    if not comments_url:
        owner = repo_data.get("owner", {}).get("login")
        repo_name = repo_data.get("name")
        comments_url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{pr_number}/comments"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(comments_url, headers=headers, json={"body": comment_body}, timeout=10.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.error(f"Failed to post comment to PR {pr_number}: {exc}")
            return None

    return {"commented": True, "predictions_count": len(surfaced_preds), "body": comment_body}


def _urls_match(url1: str, url2: str) -> bool:
    """Compare two git repo URLs, normalizing protocols and suffixes."""
    def _normalize(u: str) -> str:
        u = u.strip().rstrip("/")
        if u.endswith(".git"):
            u = u[:-4]
        for prefix in ("https://", "http://", "git@", "ssh://"):
            if u.startswith(prefix):
                u = u[len(prefix):]
        u = u.replace(":", "/")
        if u.startswith("www."):
            u = u[4:]
        return u
    return _normalize(url1) == _normalize(url2)


def render_pr_comment(predictions: list[dict]) -> str:
    """Generate Markdown text comment body for a list of predictions."""
    lines = [
        "### 🔍 AHAL PR Blast-Radius Predictions",
        "",
        "Based on the files modified in this PR, AHAL has identified potential affected components that may also require updates or verification.",
        "",
        "| Target Component | Raw Score | Calibrated Confidence | Basis |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for p in predictions:
        raw_pct = f"{p['score'] * 100:.1f}%"
        cal_pct = f"{p['calibrated_score'] * 100:.1f}%"
        lines.append(f"| `{p['target']}` | {raw_pct} | {cal_pct} | {p['basis']} |")

    lines.append("")
    lines.append("*Confidence scores are calibrated using per-repository historical merge data (§5.3).*")
    return "\n".join(lines)
