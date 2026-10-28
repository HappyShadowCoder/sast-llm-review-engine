from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


CategoryType = Literal["architecture", "security", "performance", "concurrency", "bug"]
SeverityType = Literal["critical", "high", "medium"]
CommentStatusType = Literal["pending", "accepted", "dismissed"]


class ReviewFinding(BaseModel):
    file_path: str = Field(..., description="Target file path relative to repo root")
    start_line: int = Field(..., ge=1, description="1-based starting line number")
    end_line: int = Field(..., ge=1, description="1-based ending line number")
    category: CategoryType = Field(..., description="Issue category")
    severity: SeverityType = Field(..., description="Issue severity")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    explanation: str = Field(..., min_length=1, description="Clear technical explanation of the issue")
    suggested_code: str = Field(..., description="Exact replacement block for lines [start_line, end_line]")

    @field_validator("end_line")
    @classmethod
    def validate_line_range(cls, v: int, info) -> int:
        start_line = info.data.get("start_line")
        if start_line is not None and v < start_line:
            raise ValueError(f"end_line ({v}) cannot be less than start_line ({start_line})")
        return v

    def is_noise(self, min_confidence: float = 0.80) -> bool:
        """Anti-noise gate: drop any finding below threshold confidence."""
        return self.confidence < min_confidence


class ReviewCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_run_id: str
    external_comment_id: Optional[str]
    file_path: str
    start_line: int
    end_line: int
    category: str
    severity: str
    confidence: float
    suggestion_body: str
    status: CommentStatusType
    created_at: datetime
    updated_at: datetime


class CommentFeedbackUpdate(BaseModel):
    status: Literal["accepted", "dismissed"]
    reason: Optional[str] = None


class LiveScanRequest(BaseModel):
    pr_url: str = Field(..., description="Full GitHub Pull Request URL or repository URL")
    github_token: Optional[str] = Field(None, description="Optional GitHub Personal Access Token")
    post_to_github: bool = Field(False, description="Whether to post inline comments to the PR")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (overrides OPENAI_API_KEY env var)")
    model: str = Field("gpt-4o-mini", description="OpenAI model name to use for AI review")


class ASTScopeSummary(BaseModel):
    name: str
    kind: str
    start_line: int
    end_line: int
    called_symbols: List[str] = Field(default_factory=list)
    imported_symbols: List[str] = Field(default_factory=list)


class ScannedFileSummary(BaseModel):
    file_path: str
    scopes: List[ASTScopeSummary] = Field(default_factory=list)
    symbols_count: int = 0
    sast_alerts_count: int = 0


class LiveScanFinding(BaseModel):
    id: str
    file_path: str
    start_line: int
    end_line: int
    category: str
    severity: str
    confidence: float
    explanation: str
    suggested_code: str
    status: str = "pending"


class LiveScanResponse(BaseModel):
    pr_title: str
    pr_author: str
    pr_url: str
    repository: str
    head_sha: str
    base_sha: str
    files_scanned: List[ScannedFileSummary] = Field(default_factory=list)
    findings: List[LiveScanFinding] = Field(default_factory=list)
    posted_to_github: bool = False
    total_findings: int = 0
    scan_duration_ms: int = 0
    ai_engine_used: str = "AST+SAST (Deterministic)"
    tokens_used: int = 0
    llm_prompt_preview: Optional[str] = None


class RepoAnalysisRequest(BaseModel):
    git_url: str = Field(..., description="Full GitHub repository or pull request URL")
    provider: Literal["openai", "gemini"] = Field("openai", description="AI provider to use ('openai' or 'gemini')")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API key")
    github_token: Optional[str] = Field(None, description="Optional GitHub Personal Access Token")
    model: Optional[str] = Field(None, description="Model override (e.g. gpt-4o-mini, gpt-4o, gemini-2.5-flash, gemini-2.5-pro)")


class RepoSummary(BaseModel):
    owner: str
    name: str
    description: Optional[str] = None
    stars: int = 0
    forks: int = 0
    default_branch: str = "main"
    languages: dict[str, int] = Field(default_factory=dict)
    health_score: int = Field(..., ge=0, le=100)
    executive_summary: str
    analyzed_target: str
    target_type: Literal["repository", "pull_request"]


class CommitReportItem(BaseModel):
    sha: str
    short_sha: str
    author: str
    date: str
    message: str
    impact_note: str
    risk_level: Literal["low", "medium", "high"]
    files_changed_count: int
    html_url: str


class PRReportItem(BaseModel):
    number: int
    title: str
    author: str
    state: str
    created_at: str
    branch: str
    review_readiness: str
    summary: str
    html_url: str


class CodeCorrection(BaseModel):
    id: str
    file_path: str
    start_line: int
    end_line: int
    severity: Literal["critical", "high", "medium"]
    category: Literal["architecture", "security", "performance", "concurrency", "bug"]
    confidence: float
    explanation: str
    original_code: str
    corrected_code: str


class CouplingHotspot(BaseModel):
    file_path: str
    reason: str
    risk_score: float
    callers: List[str] = Field(default_factory=list)


class ScalabilityBottleneck(BaseModel):
    title: str
    description: str
    recommendation: str
    severity: Literal["critical", "high", "medium"]


class ArchitectureAdvice(BaseModel):
    overall_critique: str
    coupling_hotspots: List[CouplingHotspot] = Field(default_factory=list)
    scalability_bottlenecks: List[ScalabilityBottleneck] = Field(default_factory=list)
    refactoring_recommendations: List[str] = Field(default_factory=list)
    design_patterns_advice: List[str] = Field(default_factory=list)


class ASTInsights(BaseModel):
    total_symbols: int
    classes_count: int
    functions_count: int
    classes: List[dict] = Field(default_factory=list)
    functions: List[dict] = Field(default_factory=list)
    dependency_map: List[dict] = Field(default_factory=list)


class FileTreeItem(BaseModel):
    path: str
    type: Literal["file", "directory"]
    size_bytes: Optional[int] = None
    symbols_count: int = 0
    issues_count: int = 0
    content: Optional[str] = None


class RepoAnalysisReport(BaseModel):
    repo_summary: RepoSummary
    commits_report: List[CommitReportItem] = Field(default_factory=list)
    prs_report: List[PRReportItem] = Field(default_factory=list)
    code_corrections: List[CodeCorrection] = Field(default_factory=list)
    architecture_advice: ArchitectureAdvice
    ast_insights: ASTInsights
    file_tree: List[FileTreeItem] = Field(default_factory=list)
    ai_provider_used: str
    ai_model_used: str
    analysis_duration_ms: int


class PublishPRReviewRequest(BaseModel):
    pr_url: str = Field(..., description="Target GitHub PR URL")
    github_token: str = Field(..., description="GitHub Personal Access Token")
    findings: List[CodeCorrection] = Field(default_factory=list)
    summary_body: Optional[str] = None


class PublishPRReviewResponse(BaseModel):
    success: bool
    comments_posted: int
    review_url: str
    message: str


class CreateFixPRRequest(BaseModel):
    git_url: str = Field(..., description="Target GitHub repo or PR URL")
    github_token: str = Field(..., description="GitHub Personal Access Token")
    correction: CodeCorrection
    branch_name: Optional[str] = None
    pr_title: Optional[str] = None


class CreateFixPRResponse(BaseModel):
    success: bool
    pr_url: str
    branch_name: str
    message: str


class ExportReportRequest(BaseModel):
    format: Literal["sarif", "markdown"]
    report: RepoAnalysisReport


class ExportReportResponse(BaseModel):
    content: str
    filename: str
    content_type: str



