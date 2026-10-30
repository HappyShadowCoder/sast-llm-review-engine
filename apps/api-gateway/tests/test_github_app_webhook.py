import hashlib
import hmac
import json
import time
from typing import Any, Dict, List
import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Response
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import PullRequest, Repository, ReviewComment, ReviewRun
from src.schemas.review import LiveScanFinding
from src.services.github_app_auth import GitHubAppAuthService
from src.services.github_review_service import (
    GitHubReviewService,
    build_review_summary_body,
    map_findings_to_diff,
)


def compute_github_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def generate_test_rsa_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture(scope="module")
def rsa_private_key_pem() -> str:
    return generate_test_rsa_pem()


# -------------------------------------------------------------------------
# 1. Signature Verification Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_valid_signature_accepted(client: AsyncClient, db_session: AsyncSession):
    secret = "test_github_secret_key_123"
    payload = {
        "action": "opened",
        "number": 201,
        "pull_request": {
            "number": 201,
            "title": "Add auth middleware",
            "user": {"login": "dev_alice"},
            "head": {"sha": "sha_valid_1", "ref": "feat/auth"},
            "base": {"sha": "sha_base_1", "ref": "main"},
            "draft": False,
        },
        "repository": {
            "id": 112233,
            "full_name": "acme/api-service",
            "default_branch": "main",
        },
        "installation": {"id": 9988},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"
    assert data["review_run_id"] is not None


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    payload = {"action": "opened", "number": 1}
    body = json.dumps(payload).encode("utf-8")

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=invalidhexsignature000000000000000000000000000000000000000000000000",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 401
    assert "Invalid GitHub webhook signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client: AsyncClient):
    payload = {"action": "opened", "number": 1}
    body = json.dumps(payload).encode("utf-8")

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 401
    assert "Missing X-Hub-Signature-256 header" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_ping_event(client: AsyncClient):
    secret = "test_github_secret_key_123"
    payload = {"zen": "Keep it logically awesome."}
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "success"
    assert "Pong" in res.json()["message"]


# -------------------------------------------------------------------------
# 2. Event Filtering Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_ignores_draft_pr(client: AsyncClient):
    secret = "test_github_secret_key_123"
    payload = {
        "action": "opened",
        "number": 202,
        "pull_request": {
            "number": 202,
            "title": "WIP: Work in progress",
            "user": {"login": "dev_bob"},
            "head": {"sha": "sha_draft_1"},
            "draft": True,
        },
        "repository": {"id": 112233, "full_name": "acme/api-service"},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "ignored"
    assert "Draft" in res.json()["message"]


@pytest.mark.asyncio
async def test_webhook_ignores_bot_pr(client: AsyncClient):
    secret = "test_github_secret_key_123"
    payload = {
        "action": "opened",
        "number": 203,
        "pull_request": {
            "number": 203,
            "title": "Bump dependencies",
            "user": {"login": "dependabot[bot]", "type": "Bot"},
            "head": {"sha": "sha_bot_1"},
            "draft": False,
        },
        "repository": {"id": 112233, "full_name": "acme/api-service"},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "ignored"
    assert "Bot" in res.json()["message"]


@pytest.mark.asyncio
async def test_webhook_ignores_non_actionable_actions(client: AsyncClient):
    secret = "test_github_secret_key_123"
    payload = {
        "action": "labeled",
        "number": 204,
        "pull_request": {
            "number": 204,
            "title": "Some feature",
            "user": {"login": "dev_alice"},
            "head": {"sha": "sha_label_1"},
            "draft": False,
        },
        "repository": {"id": 112233, "full_name": "acme/api-service"},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "ignored"


# -------------------------------------------------------------------------
# 3. Idempotency Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_idempotency_same_sha_ignored(client: AsyncClient, db_session: AsyncSession):
    secret = "test_github_secret_key_123"
    head_sha = "sha_idempotent_12345"

    # Pre-seed Repository and PR with completed ReviewRun
    repo = Repository(
        vcs_provider="github",
        external_repo_id="778899",
        name="acme/idempotent-repo",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        repo_id=repo.id,
        pr_number=305,
        title="Payment refactor",
        author="dev_charlie",
        head_sha=head_sha,
        base_sha="base_123",
        status="open",
    )
    db_session.add(pr)
    await db_session.flush()

    run = ReviewRun(
        pr_id=pr.id,
        head_sha=head_sha,
        status="completed",
        latency_ms=1200,
    )
    db_session.add(run)
    await db_session.commit()

    # Now deliver webhook for the same PR with the exact same head SHA
    payload = {
        "action": "synchronize",
        "number": 305,
        "pull_request": {
            "number": 305,
            "title": "Payment refactor",
            "user": {"login": "dev_charlie"},
            "head": {"sha": head_sha},
            "base": {"sha": "base_123"},
            "draft": False,
        },
        "repository": {
            "id": 778899,
            "full_name": "acme/idempotent-repo",
            "default_branch": "main",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = compute_github_sig(body, secret)

    res = await client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "ignored"
    assert "already been reviewed" in data["message"]


# -------------------------------------------------------------------------
# 4. GitHub App Auth Tests (JWT, Token Exchange, Cache)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_app_jwt_and_token_caching(rsa_private_key_pem: str):
    auth_service = GitHubAppAuthService(
        app_id="999888",
        private_key=rsa_private_key_pem,
        api_base="https://api.github.com",
    )

    # 1. Test JWT generation
    jwt_token = auth_service.generate_app_jwt(expiration_seconds=300)
    assert isinstance(jwt_token, str)
    assert len(jwt_token) > 50

    call_count = 0

    def mock_handler(request):
        nonlocal call_count
        call_count += 1
        if "access_tokens" in str(request.url):
            return Response(
                201,
                json={
                    "token": "ghs_mocked_installation_token_xyz",
                    "expires_at": "2030-01-01T00:00:00Z",
                },
            )
        return Response(404)

    mock_client = AsyncClient(transport=MockTransport(mock_handler))

    # First call -> hits mock endpoint
    tok1 = await auth_service.get_installation_token(installation_id="12345", client=mock_client)
    assert tok1 == "ghs_mocked_installation_token_xyz"
    assert call_count == 1

    # Second call -> returned from in-memory cache, call_count does not increase
    tok2 = await auth_service.get_installation_token(installation_id="12345", client=mock_client)
    assert tok2 == "ghs_mocked_installation_token_xyz"
    assert call_count == 1


# -------------------------------------------------------------------------
# 5. Line-to-Position Mapping & Out-of-Diff Findings Tests
# -------------------------------------------------------------------------

class MockDiffHunk:
    def __init__(self, new_start: int, new_lines: int, modified_lines: List[int]):
        self.new_start = new_start
        self.new_lines = new_lines
        self.modified_lines = modified_lines


class MockFileDiff:
    def __init__(self, new_path: str, hunks: List[MockDiffHunk]):
        self.new_path = new_path
        self.hunks = hunks


def test_line_to_diff_position_mapping():
    file_diffs = [
        MockFileDiff(
            new_path="src/auth.py",
            hunks=[
                MockDiffHunk(new_start=10, new_lines=10, modified_lines=[12, 13, 14]),
            ],
        ),
        MockFileDiff(
            new_path="src/payments.py",
            hunks=[
                MockDiffHunk(new_start=50, new_lines=5, modified_lines=[51, 52]),
            ],
        ),
    ]

    findings = [
        # In diff: src/auth.py line 12
        LiveScanFinding(
            id="f1",
            file_path="src/auth.py",
            start_line=12,
            end_line=12,
            category="security",
            severity="critical",
            confidence=0.95,
            explanation="SQL Injection vulnerability",
            suggested_code="db.execute(query, params)",
        ),
        # Out of diff: src/auth.py line 90 (outside hunk 10-20)
        LiveScanFinding(
            id="f2",
            file_path="src/auth.py",
            start_line=90,
            end_line=90,
            category="architecture",
            severity="high",
            confidence=0.85,
            explanation="Missing abstract interface",
            suggested_code="class BaseAuth(ABC): ...",
        ),
        # Out of diff: untouched file
        LiveScanFinding(
            id="f3",
            file_path="src/config.py",
            start_line=5,
            end_line=5,
            category="bug",
            severity="medium",
            confidence=0.82,
            explanation="Unused variable",
            suggested_code="",
        ),
        # In diff: src/payments.py line 51, but previously flagged
        LiveScanFinding(
            id="f4",
            file_path="src/payments.py",
            start_line=51,
            end_line=51,
            category="performance",
            severity="medium",
            confidence=0.88,
            explanation="N+1 query",
            suggested_code="",
        ),
    ]

    existing_fingerprints = {("src/payments.py", 51, "performance")}

    inline_comments, out_of_diff = map_findings_to_diff(
        findings=findings,
        file_diffs=file_diffs,
        existing_fingerprints=existing_fingerprints,
    )

    # Finding 1 is in diff -> inline
    assert len(inline_comments) == 1
    assert inline_comments[0]["path"] == "src/auth.py"
    assert inline_comments[0]["line"] == 12
    assert "SQL Injection" in inline_comments[0]["body"]
    assert "```suggestion" in inline_comments[0]["body"]

    # Finding 4 was skipped because it's in existing_fingerprints (synchronize dedup)
    paths_in_inline = [c["path"] for c in inline_comments]
    assert "src/payments.py" not in paths_in_inline

    # Finding 2 and 3 are out-of-diff -> returned in out_of_diff
    assert len(out_of_diff) == 2
    out_paths = {f.file_path for f in out_of_diff}
    assert "src/auth.py" in out_paths
    assert "src/config.py" in out_paths

    # Verify summary markdown construction incorporates out-of-diff findings
    summary = build_review_summary_body(
        head_sha="abcdef123456",
        total_findings=4,
        inline_count=len(inline_comments),
        out_of_diff_findings=out_of_diff,
    )
    assert "## 🤖 AICR Automated Code Review" in summary
    assert "Additional Findings (Outside PR Diff)" in summary
    assert "src/auth.py:90" in summary
    assert "src/config.py:5" in summary


# -------------------------------------------------------------------------
# 6. Post Review (ONE review call) Mocking Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_review_single_api_call():
    review_posted_payload = {}

    def mock_github(request):
        nonlocal review_posted_payload
        if "/reviews" in str(request.url):
            review_posted_payload = json.loads(request.content.decode("utf-8"))
            return Response(200, json={"id": 8877, "state": "COMMENTED"})
        return Response(404)

    mock_client = AsyncClient(transport=MockTransport(mock_github))

    inline = [{"path": "src/app.py", "line": 20, "body": "Fix this"}]
    summary = "Review summary body text"

    success = await GitHubReviewService.post_review(
        owner="test-org",
        repo="test-repo",
        pr_number=42,
        head_sha="sha_test_head_99",
        inline_comments=inline,
        summary_body=summary,
        token="ghs_dummy_token",
        client=mock_client,
    )

    assert success is True
    assert review_posted_payload["commit_id"] == "sha_test_head_99"
    assert review_posted_payload["event"] == "COMMENT"
    assert review_posted_payload["body"] == summary
    assert len(review_posted_payload["comments"]) == 1
    assert review_posted_payload["comments"][0]["path"] == "src/app.py"
    assert review_posted_payload["comments"][0]["line"] == 20


# -------------------------------------------------------------------------
# 7. End-to-End Review Task & DB Telemetry Persistence Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_github_review_task_e2e_persistence(
    db_session: AsyncSession,
    rsa_private_key_pem: str,
):
    from unittest.mock import patch

    repo = Repository(
        vcs_provider="github",
        external_repo_id="998877",
        name="acme/sample-repo",
        default_branch="main",
        installation_id="12345",
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        repo_id=repo.id,
        pr_number=15,
        title="Fix SQL vulnerability",
        author="alice",
        head_sha="sha_test_head_15",
        base_sha="sha_test_base_15",
        status="open",
    )
    db_session.add(pr)
    await db_session.flush()

    run = ReviewRun(
        pr_id=pr.id,
        head_sha="sha_test_head_15",
        status="pending",
    )
    db_session.add(run)
    await db_session.commit()

    diff_content = (
        "diff --git a/src/login.py b/src/login.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/src/login.py\n"
        "+++ b/src/login.py\n"
        "@@ -1,5 +1,7 @@\n"
        " def check_auth(user, password):\n"
        "+    # Security issue check\n"
        "+    return user == 'admin'\n"
    )

    review_call_captured = {}

    def mock_github_routes(request):
        url = str(request.url)
        if "access_tokens" in url:
            return Response(201, json={"token": "ghs_test_token_789", "expires_at": "2030-01-01T00:00:00Z"})
        if "/pulls/15/files" in url:
            return Response(200, json=[{"filename": "src/login.py", "patch": diff_content}])
        if "/pulls/15/reviews" in url:
            review_call_captured.update(json.loads(request.content.decode("utf-8")))
            return Response(200, json={"id": 9911, "state": "COMMENTED"})
        if "/pulls/15" in url:
            if "diff" in request.headers.get("Accept", ""):
                return Response(200, text=diff_content)
            return Response(200, json={
                "number": 15,
                "title": "Fix SQL vulnerability",
                "user": {"login": "alice"},
                "head": {"sha": "sha_test_head_15"},
                "base": {"sha": "sha_test_base_15"},
            })
        return Response(404)

    mock_client = AsyncClient(transport=MockTransport(mock_github_routes))

    with patch("src.services.github_review_service.github_app_auth._private_key", rsa_private_key_pem), \
         patch("src.services.github_review_service.github_app_auth._app_id", "12345"):
        await GitHubReviewService.execute_github_review_task(
            review_run_id=run.id,
            repo_name="acme/sample-repo",
            pr_number=15,
            head_sha="sha_test_head_15",
            installation_id="12345",
            db_session=db_session,
            client=mock_client,
        )

    # Verify review was posted to GitHub
    assert "commit_id" in review_call_captured
    assert review_call_captured["commit_id"] == "sha_test_head_15"
    assert "## 🤖 AICR Automated Code Review" in review_call_captured["body"]

    # Verify DB persistence of ReviewRun and ReviewComments
    refreshed_run = (
        await db_session.execute(select(ReviewRun).where(ReviewRun.id == run.id))
    ).scalars().first()
    assert refreshed_run.status == "completed"
    assert refreshed_run.latency_ms > 0

    comments = (
        await db_session.execute(select(ReviewComment).where(ReviewComment.review_run_id == run.id))
    ).scalars().all()
    assert len(comments) >= 1
    for c in comments:
        assert c.file_path is not None
        assert c.category in {"architecture", "security", "performance", "concurrency", "bug"}
        assert c.confidence >= 0.80

