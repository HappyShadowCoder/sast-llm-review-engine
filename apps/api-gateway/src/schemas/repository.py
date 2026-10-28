from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vcs_provider: str
    external_repo_id: str
    name: str
    default_branch: str
    installation_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repo_id: str
    pr_number: int
    title: str
    author: str
    head_sha: str
    base_sha: str
    status: str
    opened_at: datetime
    merged_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ReviewRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pr_id: str
    head_sha: str
    status: str
    latency_ms: Optional[int]
    tokens_used: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
