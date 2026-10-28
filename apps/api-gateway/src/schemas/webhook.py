from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class NormalizedPREvent(BaseModel):
    vcs_provider: Literal["github", "gitlab"]
    event_type: str = Field(description="Normalized event name, e.g. pull_request.opened, merge_request.open")
    action: str = Field(description="Action name, e.g. opened, synchronize, reopened, update")
    external_repo_id: str
    repo_name: str
    repo_default_branch: str = "main"
    repo_clone_url: Optional[str] = None
    installation_id: Optional[str] = None
    pr_number: int
    title: str
    author: str
    head_sha: str
    base_sha: str
    head_branch: str
    base_branch: str
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    merged_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None


class NormalizedFeedbackEvent(BaseModel):
    vcs_provider: Literal["github", "gitlab"]
    event_type: str = Field(description="e.g. pull_request_review_comment, pull_request_review_thread, note")
    action: str
    external_comment_id: Optional[str] = None
    external_repo_id: Optional[str] = None
    pr_number: Optional[int] = None
    status: Literal["accepted", "dismissed"]
    reason: str = Field(description="Why status was updated (reaction, thread_resolved, suggestion_applied, etc.)")
    raw_payload: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    status: str
    message: str
    event_type: Optional[str] = None
    review_run_id: Optional[str] = None
    comment_id: Optional[str] = None
