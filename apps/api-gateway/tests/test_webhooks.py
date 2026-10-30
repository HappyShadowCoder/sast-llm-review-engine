import json
import hmac
import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Repository, PullRequest, ReviewRun, ReviewComment


def compute_github_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_github_webhook_pull_request_flow(client: AsyncClient, db_session: AsyncSession):
    secret = "test_github_secret_key_123"
    payload = {
        "action": "opened",
        "number": 101,
        "pull_request": {
            "number": 101,
            "title": "Optimize Redis connection pool",
            "user": {"login": "perf_lead"},
            "head": {"sha": "sha_head_101", "ref": "feat/redis-pool"},
            "base": {"sha": "sha_base_101", "ref": "main"},
            "created_at": "2026-10-20T14:00:00Z",
        },
        "repository": {
            "id": 990011,
            "full_name": "enterprise/core-api",
            "default_branch": "main",
            "clone_url": "https://github.com/enterprise/core-api.git",
        },
        "installation": {"id": 5544},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    response = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code in (200, 202)
    res_data = response.json()
    assert res_data["status"] == "enqueued"
    assert res_data["review_run_id"] is not None

    # Verify repository was created
    repo_res = await db_session.execute(
        select(Repository).where(Repository.external_repo_id == "990011")
    )
    repo = repo_res.scalars().first()
    assert repo is not None
    assert repo.name == "enterprise/core-api"
    assert repo.vcs_provider == "github"

    # Verify pull request was created
    pr_res = await db_session.execute(
        select(PullRequest).where(PullRequest.pr_number == 101)
    )
    pr = pr_res.scalars().first()
    assert pr is not None
    assert pr.author == "perf_lead"
    assert pr.head_sha == "sha_head_101"

    # Verify review run was created
    run_res = await db_session.execute(
        select(ReviewRun).where(ReviewRun.id == res_data["review_run_id"])
    )
    run = run_res.scalars().first()
    assert run is not None
    assert run.status == "pending"


@pytest.mark.asyncio
async def test_github_webhook_feedback_flow(client: AsyncClient, db_session: AsyncSession):
    secret = "test_github_secret_key_123"

    # Pre-populate review comment
    repo = Repository(vcs_provider="github", external_repo_id="7788", name="org/app", default_branch="main")
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(repo_id=repo.id, pr_number=33, title="Refactor", author="dev", head_sha="h1", base_sha="b1")
    db_session.add(pr)
    await db_session.flush()

    run = ReviewRun(pr_id=pr.id, head_sha="h1", status="completed")
    db_session.add(run)
    await db_session.flush()

    comment = ReviewComment(
        review_run_id=run.id,
        external_comment_id="comment_gh_555",
        file_path="src/utils.py",
        start_line=1,
        end_line=5,
        category="architecture",
        severity="medium",
        confidence=0.88,
        suggestion_body="Extract utility function",
        status="pending",
    )
    db_session.add(comment)
    await db_session.commit()

    # Send thread resolved feedback event
    feedback_payload = {
        "action": "resolved",
        "thread": {"comments": [{"id": 555}]},
        "repository": {"id": 7788},
    }
    body = json.dumps(feedback_payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    response = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request_review_thread",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code in (200, 202)
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "status=accepted" in res_data["message"]

    # Verify comment was updated in DB
    comment_check = (await db_session.execute(select(ReviewComment).where(ReviewComment.id == comment.id))).scalars().first()
    assert comment_check.status == "accepted"


@pytest.mark.asyncio
async def test_gitlab_webhook_merge_request_flow(client: AsyncClient, db_session: AsyncSession):
    token = "test_gitlab_secret_token_456"
    payload = {
        "object_kind": "merge_request",
        "user": {"username": "gitlab_architect"},
        "project": {
            "id": 8800,
            "name": "payment-gateway",
            "path_with_namespace": "fintech/payment-gateway",
            "default_branch": "main",
            "git_http_url": "https://gitlab.com/fintech/payment-gateway.git",
        },
        "object_attributes": {
            "id": 401,
            "iid": 22,
            "title": "Idempotent charge handling",
            "action": "open",
            "state": "opened",
            "last_commit": {"id": "gl_head_sha_99"},
            "source_branch": "feat/idempotency",
            "target_branch": "main",
            "source_branch_sha": "gl_head_sha_99",
            "target_branch_sha": "gl_base_sha_00",
            "created_at": "2026-10-20 15:00:00 UTC",
        },
    }
    body = json.dumps(payload).encode("utf-8")

    response = await client.post(
        "/webhooks/gitlab",
        content=body,
        headers={
            "X-Gitlab-Token": token,
            "X-Gitlab-Event": "Merge Request Hook",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code in (200, 202)
    res_data = response.json()
    assert res_data["status"] == "enqueued"

    # Verify repository was created
    repo_res = await db_session.execute(
        select(Repository).where(Repository.external_repo_id == "8800")
    )
    repo = repo_res.scalars().first()
    assert repo is not None
    assert repo.vcs_provider == "gitlab"

    # Verify MR was created
    pr_res = await db_session.execute(
        select(PullRequest).where(PullRequest.pr_number == 22)
    )
    pr = pr_res.scalars().first()
    assert pr is not None
    assert pr.author == "gitlab_architect"


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature_rejected(client: AsyncClient):
    body = b'{"action": "opened"}'
    response = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=wrongsignature00000000000000000000000000000000000000000000000000",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gitlab_webhook_invalid_token_rejected(client: AsyncClient):
    body = b'{"object_kind": "merge_request"}'
    response = await client.post(
        "/webhooks/gitlab",
        content=body,
        headers={
            "X-Gitlab-Token": "wrong_token",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401
