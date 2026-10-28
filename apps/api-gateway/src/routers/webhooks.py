import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import PullRequest, Repository, ReviewComment, ReviewRun
from ..schemas.webhook import WebhookResponse
from ..schemas.review import CommentFeedbackUpdate, ReviewCommentResponse
from ..services.celery_publisher import CeleryPublisher
from ..services.feedback_handler import FeedbackHandler
from ..services.payload_normalizer import PayloadNormalizer
from ..services.signature_validator import (
    verify_github_signature,
    verify_gitlab_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["webhooks"])


@router.post("/webhooks/github", response_model=WebhookResponse)
async def handle_github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header("pull_request", alias="X-GitHub-Event"),
):
    raw_body = await request.body()
    verify_github_signature(
        raw_body=raw_body,
        signature_header=x_hub_signature_256,
        secret=settings.GITHUB_WEBHOOK_SECRET,
    )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse GitHub JSON payload: {e}")
        return WebhookResponse(status="error", message="Invalid JSON payload")

    # 1. Check for review comment / thread feedback events (for DPO dataset)
    feedback_event = PayloadNormalizer.normalize_github_feedback(payload, x_github_event)
    if feedback_event:
        comment = await FeedbackHandler.process_feedback_event(db, feedback_event)
        comment_id = comment.id if comment else None
        return WebhookResponse(
            status="success",
            message=f"Feedback processed: status={feedback_event.status}",
            event_type=x_github_event,
            comment_id=comment_id,
        )

    # 2. Check for pull request events to review
    pr_event = PayloadNormalizer.normalize_github_pr(payload, x_github_event)
    if not pr_event:
        action = payload.get("action", "unknown")
        return WebhookResponse(
            status="ignored",
            message=f"GitHub event '{x_github_event}' with action '{action}' not actionable for review",
            event_type=x_github_event,
        )

    # Upsert Repository
    repo_stmt = select(Repository).where(
        Repository.vcs_provider == "github",
        Repository.external_repo_id == pr_event.external_repo_id,
    )
    repo = (await db.execute(repo_stmt)).scalars().first()
    if not repo:
        repo = Repository(
            vcs_provider="github",
            external_repo_id=pr_event.external_repo_id,
            name=pr_event.repo_name,
            default_branch=pr_event.repo_default_branch,
            installation_id=pr_event.installation_id,
        )
        db.add(repo)
        await db.flush()
    else:
        repo.name = pr_event.repo_name
        repo.default_branch = pr_event.repo_default_branch
        if pr_event.installation_id:
            repo.installation_id = pr_event.installation_id

    # Upsert PullRequest
    pr_stmt = select(PullRequest).where(
        PullRequest.repo_id == repo.id,
        PullRequest.pr_number == pr_event.pr_number,
    )
    pr = (await db.execute(pr_stmt)).scalars().first()
    if not pr:
        pr = PullRequest(
            repo_id=repo.id,
            pr_number=pr_event.pr_number,
            title=pr_event.title,
            author=pr_event.author,
            head_sha=pr_event.head_sha,
            base_sha=pr_event.base_sha,
            status="open",
            opened_at=pr_event.opened_at,
            merged_at=pr_event.merged_at,
        )
        db.add(pr)
        await db.flush()
    else:
        pr.title = pr_event.title
        pr.head_sha = pr_event.head_sha
        pr.base_sha = pr_event.base_sha
        if pr_event.merged_at:
            pr.status = "merged"
            pr.merged_at = pr_event.merged_at

    # Create ReviewRun
    review_run = ReviewRun(
        pr_id=pr.id,
        head_sha=pr_event.head_sha,
        status="pending",
    )
    db.add(review_run)
    await db.flush()

    # Enqueue Celery task
    task_id = CeleryPublisher.enqueue_review_job(
        review_run_id=review_run.id,
        repo_id=repo.id,
        pr_number=pr.pr_number,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        clone_url=pr_event.repo_clone_url or "",
    )

    return WebhookResponse(
        status="enqueued",
        message=f"Review job dispatched with task id: {task_id}",
        event_type=pr_event.event_type,
        review_run_id=review_run.id,
    )


@router.post("/webhooks/gitlab", response_model=WebhookResponse)
async def handle_gitlab_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gitlab_token: Optional[str] = Header(None, alias="X-Gitlab-Token"),
    x_gitlab_event: Optional[str] = Header("Merge Request Hook", alias="X-Gitlab-Event"),
):
    raw_body = await request.body()
    verify_gitlab_token(
        token_header=x_gitlab_token,
        expected_secret=settings.GITLAB_WEBHOOK_SECRET,
    )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse GitLab JSON payload: {e}")
        return WebhookResponse(status="error", message="Invalid JSON payload")

    # 1. Check for Note/Discussion feedback events
    feedback_event = PayloadNormalizer.normalize_gitlab_feedback(payload)
    if feedback_event:
        comment = await FeedbackHandler.process_feedback_event(db, feedback_event)
        comment_id = comment.id if comment else None
        return WebhookResponse(
            status="success",
            message=f"GitLab feedback processed: status={feedback_event.status}",
            event_type=x_gitlab_event,
            comment_id=comment_id,
        )

    # 2. Check for Merge Request events
    mr_event = PayloadNormalizer.normalize_gitlab_mr(payload)
    if not mr_event:
        return WebhookResponse(
            status="ignored",
            message=f"GitLab event '{x_gitlab_event}' not actionable for review",
            event_type=x_gitlab_event,
        )

    # Upsert Repository
    repo_stmt = select(Repository).where(
        Repository.vcs_provider == "gitlab",
        Repository.external_repo_id == mr_event.external_repo_id,
    )
    repo = (await db.execute(repo_stmt)).scalars().first()
    if not repo:
        repo = Repository(
            vcs_provider="gitlab",
            external_repo_id=mr_event.external_repo_id,
            name=mr_event.repo_name,
            default_branch=mr_event.repo_default_branch,
            installation_id=None,
        )
        db.add(repo)
        await db.flush()
    else:
        repo.name = mr_event.repo_name
        repo.default_branch = mr_event.repo_default_branch

    # Upsert PullRequest (Merge Request)
    pr_stmt = select(PullRequest).where(
        PullRequest.repo_id == repo.id,
        PullRequest.pr_number == mr_event.pr_number,
    )
    pr = (await db.execute(pr_stmt)).scalars().first()
    if not pr:
        pr = PullRequest(
            repo_id=repo.id,
            pr_number=mr_event.pr_number,
            title=mr_event.title,
            author=mr_event.author,
            head_sha=mr_event.head_sha,
            base_sha=mr_event.base_sha,
            status="open",
            opened_at=mr_event.opened_at,
            merged_at=None,
        )
        db.add(pr)
        await db.flush()
    else:
        pr.title = mr_event.title
        pr.head_sha = mr_event.head_sha
        pr.base_sha = mr_event.base_sha

    # Create ReviewRun
    review_run = ReviewRun(
        pr_id=pr.id,
        head_sha=mr_event.head_sha,
        status="pending",
    )
    db.add(review_run)
    await db.flush()

    # Enqueue Celery task
    task_id = CeleryPublisher.enqueue_review_job(
        review_run_id=review_run.id,
        repo_id=repo.id,
        pr_number=pr.pr_number,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        clone_url=mr_event.repo_clone_url or "",
    )

    return WebhookResponse(
        status="enqueued",
        message=f"GitLab review job dispatched with task id: {task_id}",
        event_type=mr_event.event_type,
        review_run_id=review_run.id,
    )


@router.post("/api/v1/comments/{comment_id}/feedback", response_model=ReviewCommentResponse)
async def submit_comment_feedback(
    comment_id: str,
    feedback: CommentFeedbackUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Direct feedback endpoint for UI dashboard or external webhook integration.
    Updates review_comments.status to accepted or dismissed.
    """
    comment = await FeedbackHandler.update_comment_status_direct(
        session=db,
        comment_id=comment_id,
        new_status=feedback.status,
    )
    if not comment:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review comment {comment_id} not found",
        )
    return comment
