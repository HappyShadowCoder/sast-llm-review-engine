from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.review import (
    CreateFixPRRequest,
    CreateFixPRResponse,
    ExportReportRequest,
    ExportReportResponse,
    LiveScanRequest,
    LiveScanResponse,
    PublishPRReviewRequest,
    PublishPRReviewResponse,
    RepoAnalysisReport,
    RepoAnalysisRequest,
)
from ..services.pr_scanner import PRScannerService
from ..services.repo_analyzer import RepoAnalyzerService

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("/analyze-repo", response_model=RepoAnalysisReport)
async def analyze_git_repository(
    request: RepoAnalysisRequest,
):
    """
    Deep Live Git Repository & PR Analysis:
    1. Fetches real repository metadata, stars, forks, languages, commits, PRs, and source files via GitHub REST API.
    2. Runs Tree-sitter AST symbol and dependency extraction across key source files.
    3. Runs Semgrep / deterministic SAST security scanning.
    4. Evaluates architectural health and generates concrete code corrections using AI (OpenAI or Gemini) or heuristics.
    5. Returns unified RepoAnalysisReport JSON.
    """
    try:
        report = await RepoAnalyzerService.analyze_repository(request)
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository analysis failed: {str(e)}",
        )


@router.post("/scan-github-pr", response_model=LiveScanResponse)
async def scan_live_github_pr(
    request: LiveScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Live GitHub Pull Request Scanner:
    1. Fetches real PR metadata, unified diff, and files via GitHub API.
    2. Runs Tree-sitter AST symbol and scope extraction.
    3. Executes SAST security scan (Semgrep rules).
    4. Applies anti-noise filter (confidence >= 0.80) to produce exact suggestion code blocks.
    5. Optionally publishes inline comments to the live GitHub PR.
    6. Persists findings to database so telemetry dashboard KPIs and hotspot tables update immediately.
    """
    try:
        response = await PRScannerService.scan_pull_request(request, db)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Live review scan failed: {str(e)}",
        )


@router.post("/publish-pr-review", response_model=PublishPRReviewResponse)
async def publish_live_pr_review(request: PublishPRReviewRequest):
    """Publishes line-by-line review comments directly to the target GitHub Pull Request."""
    try:
        res = await RepoAnalyzerService.publish_pr_review(request)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to publish review: {str(e)}")


@router.post("/create-fix-pr", response_model=CreateFixPRResponse)
async def create_fix_pull_request(request: CreateFixPRRequest):
    """Creates a remediation branch, commits the suggested fix, and opens a Pull Request on GitHub."""
    try:
        res = await RepoAnalyzerService.create_fix_pr(request)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create fix PR: {str(e)}")


@router.post("/export-report", response_model=ExportReportResponse)
async def export_audit_report(request: ExportReportRequest):
    """Exports audit findings to standard SARIF v2.1.0 JSON or Markdown report."""
    try:
        res = RepoAnalyzerService.export_report(request)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to export report: {str(e)}")


