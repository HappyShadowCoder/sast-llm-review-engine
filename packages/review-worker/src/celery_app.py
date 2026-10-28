import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "aicr_worker",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


from .models import ReviewFinding, ReviewResponse, SASTFinding
from .sast_runner import SASTRunner
from .reviewer import StructuredReviewer
from .publisher import VCSPublisher


@celery_app.task(name="review_pr")
def review_pr(
    review_run_id: str,
    repo_id: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    clone_url: str = "",
    meta: dict = None,
):
    """
    Executes end-to-end review workflow:
    1. Runs Semgrep SAST security scan.
    2. Runs AI review with strict schema validation.
    3. Filters low-confidence noise (<0.80) and formatting nitpicks.
    4. Posts committable suggestion blocks to GitHub/GitLab.
    """
    logger.info(
        f"Executing review_pr: review_run_id={review_run_id}, repo={repo_id}, pr={pr_number}"
    )
    meta = meta or {}
    files = meta.get("file_contents", {})

    # 1. Deterministic SAST scan
    sast_runner = SASTRunner()
    sast_findings = sast_runner.scan_files(files)

    # 2. AI Structured Review
    reviewer = StructuredReviewer()
    ast_context = meta.get("formatted_ast_context", "No AST context provided")
    review_res = reviewer.review_pr(
        pr_title=meta.get("pr_title", "PR Review"),
        formatted_ast_context=ast_context,
        sast_findings=sast_findings,
    )

    # 3. Post-Process & Publish
    publisher = VCSPublisher()
    vcs_provider = meta.get("vcs_provider", "github")
    if vcs_provider == "gitlab":
        publish_res = publisher.publish_gitlab_review(
            project_id=repo_id,
            mr_iid=pr_number,
            head_sha=head_sha,
            summary=review_res.summary,
            findings=review_res.findings,
        )
    else:
        publish_res = publisher.publish_github_review(
            repo_owner_name=repo_id,
            pull_number=pr_number,
            head_sha=head_sha,
            summary=review_res.summary,
            findings=review_res.findings,
        )

    logger.info(f"Review completed for run {review_run_id}: {publish_res}")
    return {
        "status": "completed",
        "review_run_id": review_run_id,
        "findings_count": len(review_res.findings),
        "published_comments": publish_res.get("comments_count", 0),
        "publish_status": publish_res.get("status"),
    }
