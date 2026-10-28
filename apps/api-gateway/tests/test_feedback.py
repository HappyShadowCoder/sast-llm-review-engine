import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from src.models import Repository, PullRequest, ReviewRun, ReviewComment
from src.schemas.webhook import NormalizedFeedbackEvent
from src.services.feedback_handler import FeedbackHandler


@pytest.mark.asyncio
async def test_feedback_handler_updates_comment_status(db_session: AsyncSession):
    # Setup test repository, PR, review run, and review comment
    repo = Repository(
        vcs_provider="github",
        external_repo_id="12345",
        name="test-org/test-repo",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        repo_id=repo.id,
        pr_number=7,
        title="Fix race condition",
        author="alice",
        head_sha="head111",
        base_sha="base222",
    )
    db_session.add(pr)
    await db_session.flush()

    review_run = ReviewRun(
        pr_id=pr.id,
        head_sha="head111",
        status="completed",
    )
    db_session.add(review_run)
    await db_session.flush()

    comment = ReviewComment(
        review_run_id=review_run.id,
        external_comment_id="github_comment_999",
        file_path="src/concurrency/lock.py",
        start_line=10,
        end_line=15,
        category="concurrency",
        severity="high",
        confidence=0.92,
        suggestion_body="Use asyncio.Lock() to prevent race condition",
        status="pending",
    )
    db_session.add(comment)
    await db_session.commit()

    # 1. Test accepting feedback
    accepted_event = NormalizedFeedbackEvent(
        vcs_provider="github",
        event_type="pull_request_review_thread",
        action="resolved",
        external_comment_id="github_comment_999",
        status="accepted",
        reason="Thread resolved by user",
    )
    updated_comment = await FeedbackHandler.process_feedback_event(db_session, accepted_event)
    assert updated_comment is not None
    assert updated_comment.status == "accepted"

    # Verify persisted in database
    res = await db_session.execute(
        select(ReviewComment).where(ReviewComment.id == comment.id)
    )
    persisted = res.scalars().first()
    assert persisted.status == "accepted"

    # 2. Test dismissing feedback
    dismissed_event = NormalizedFeedbackEvent(
        vcs_provider="github",
        event_type="reaction",
        action="created",
        external_comment_id="github_comment_999",
        status="dismissed",
        reason="Negative reaction received",
    )
    updated_comment_2 = await FeedbackHandler.process_feedback_event(db_session, dismissed_event)
    assert updated_comment_2 is not None
    assert updated_comment_2.status == "dismissed"


@pytest.mark.asyncio
async def test_direct_comment_feedback_api(client: AsyncClient, db_session: AsyncSession):
    repo = Repository(
        vcs_provider="gitlab",
        external_repo_id="9988",
        name="gitlab-org/project-x",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        repo_id=repo.id,
        pr_number=5,
        title="Add auth middleware",
        author="bob",
        head_sha="head333",
        base_sha="base444",
    )
    db_session.add(pr)
    await db_session.flush()

    run = ReviewRun(pr_id=pr.id, head_sha="head333", status="completed")
    db_session.add(run)
    await db_session.flush()

    comment = ReviewComment(
        review_run_id=run.id,
        external_comment_id="gitlab_note_444",
        file_path="src/auth.py",
        start_line=20,
        end_line=25,
        category="security",
        severity="critical",
        confidence=0.98,
        suggestion_body="Enforce JWT signature validation",
        status="pending",
    )
    db_session.add(comment)
    await db_session.commit()

    # Call direct feedback endpoint
    response = await client.post(
        f"/api/v1/comments/{comment.id}/feedback",
        json={"status": "accepted", "reason": "Engineer accepted the fix"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == comment.id
    assert data["status"] == "accepted"
    assert data["category"] == "security"
