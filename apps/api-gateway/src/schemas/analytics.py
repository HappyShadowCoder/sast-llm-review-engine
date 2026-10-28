from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class OverviewMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    suggestion_acceptance_rate: float = Field(..., description="Percentage of AI suggestions committed")
    acceptance_rate_delta_30d: float = Field(..., description="Change compared to previous 30-day window")
    pre_merge_catch_rate: float = Field(..., description="Percentage of critical/high issues resolved pre-merge")
    pre_merge_catch_delta_30d: float
    median_turnaround_mins: float = Field(..., description="Median minutes from PR open to AI sign-off")
    turnaround_delta_30d: float
    noise_suppression_ratio: float = Field(..., description="Percentage of low-confidence findings suppressed")
    total_prs_reviewed: int
    total_findings_caught: int


class WeeklyDefectTrend(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week: str
    architecture: int
    security: int
    concurrency: int
    performance: int
    bug: int
    total: int


class ModelCheckpointTrend(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    acceptance_rate: float
    hallucination_rate: float
    avg_confidence: float


class TrendsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekly_defects: List[WeeklyDefectTrend]
    model_checkpoints: List[ModelCheckpointTrend]


class HotspotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_path: str
    risk_score: float
    critical_count: int
    high_count: int
    dominant_category: str
    recurring_anti_patterns: List[str]
    affected_callers_count: int
    recent_prs: List[int]


class ASTContextSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    upstream_callers: List[str] = Field(default_factory=list)
    downstream_defs: List[str] = Field(default_factory=list)


class ReviewDetailItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pr_id: str
    pr_number: int
    pr_title: str
    author: str
    head_sha: str
    file_path: str
    start_line: int
    end_line: int
    diff_snippet: str
    ast_context: ASTContextSummary
    sast_findings: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_code: str
    explanation: str
    category: str
    severity: str
    confidence: float
    status: Literal["pending", "accepted", "dismissed"]
    created_at: str
