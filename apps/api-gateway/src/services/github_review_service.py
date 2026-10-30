import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import PullRequest, Repository, ReviewComment, ReviewRun
from ..schemas.review import LiveScanFinding
from .github_app_auth import github_app_auth
from .pr_scanner import PRScannerService, _load_engine_packages

logger = logging.getLogger(__name__)


def map_findings_to_diff(
    findings: List[LiveScanFinding],
    file_diffs: List[Any],
    existing_fingerprints: Optional[Set[Tuple[str, int, str]]] = None,
) -> Tuple[List[Dict[str, Any]], List[LiveScanFinding]]:
    """
    Partitions findings into:
    1. inline_comments: findings whose end_line is within the diff hunks of the new file.
       Format: [{"path": str, "line": int, "body": str}]
    2. out_of_diff_findings: findings on lines or files outside the diff hunks.
       These will be embedded into the review summary markdown to avoid GitHub 422 errors.

    Filters out findings that match existing_fingerprints (file_path, line, category)
    to prevent duplicate review comments on 'synchronize' events.
    """
    if existing_fingerprints is None:
        existing_fingerprints = set()

    # Map each file path to set of valid diff lines
    valid_diff_lines_by_file: Dict[str, Set[int]] = {}
    for fd in file_diffs:
        p = getattr(fd, "new_path", "")
        if not p or p == "/dev/null":
            continue

        lines = set()
        for hunk in getattr(fd, "hunks", []):
            start = getattr(hunk, "new_start", 1)
            count = getattr(hunk, "new_lines", 1)
            # Lines covered in the new version by this hunk
            for line_no in range(start, start + max(1, count)):
                lines.add(line_no)
            for mod_l in getattr(hunk, "modified_lines", []):
                lines.add(mod_l)

        valid_diff_lines_by_file[p] = lines

    inline_comments: List[Dict[str, Any]] = []
    out_of_diff: List[LiveScanFinding] = []

    for f in findings:
        # Check for duplicate comment from previous reviews of this PR
        fingerprint = (f.file_path, f.end_line, f.category)
        if fingerprint in existing_fingerprints:
            logger.info(f"Skipping duplicate comment for {f.file_path}:{f.end_line} ({f.category})")
            continue

        is_in_diff = (
            f.file_path in valid_diff_lines_by_file
            and f.end_line in valid_diff_lines_by_file[f.file_path]
        )

        if is_in_diff:
            body_md = (
                f"**[AICR Code Review Assistant]** `{f.category.upper()}` "
                f"({f.severity.upper()} — {int(f.confidence * 100)}% confidence)\n\n"
                f"{f.explanation}\n\n"
                f"```suggestion\n{f.suggested_code}\n```"
            )
            inline_comments.append({
                "path": f.file_path,
                "line": f.end_line,
                "body": body_md,
            })
        else:
            out_of_diff.append(f)

    return inline_comments, out_of_diff


def build_review_summary_body(
    head_sha: str,
    total_findings: int,
    inline_count: int,
    out_of_diff_findings: List[LiveScanFinding],
) -> str:
    """Builds a formatted markdown summary for the single GitHub review."""
    status_label = "⚠️ Issues Detected" if total_findings > 0 else "✅ Passed (Clean)"

    summary = (
        f"## 🤖 AICR Automated Code Review\n\n"
        f"**Status:** {status_label}\n"
        f"- **Head Commit:** `{head_sha[:7]}`\n"
        f"- **Findings:** {total_findings} total ({inline_count} inline, {len(out_of_diff_findings)} in surrounding scope)\n"
        f"- **Anti-Noise Gate:** Enforced (confidence ≥ 80%, style nits suppressed)\n"
    )

    if out_of_diff_findings:
        summary += "\n---\n### 🔍 Additional Findings (Outside PR Diff)\n"
        summary += (
            "The following potential issues were detected in unchanged lines or related caller/callee scopes:\n\n"
        )
        for f in out_of_diff_findings:
            summary += (
                f"- **`{f.file_path}:{f.end_line}`** — `{f.category.upper()}` "
                f"({f.severity.upper()} — {int(f.confidence * 100)}% confidence)\n"
                f"  {f.explanation}\n\n"
                f"  ```suggestion\n  {f.suggested_code}\n  ```\n\n"
            )

    return summary


class GitHubReviewService:
    @classmethod
    async def post_review(
        cls,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        inline_comments: List[Dict[str, Any]],
        summary_body: str,
        token: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> bool:
        """
        Posts ONE GitHub Review (pulls/{pr_number}/reviews) with inline comments and summary body.
        If comments fail or are rejected, falls back to posting review without inline comments.
        """
        url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AICodeReviewer-Bot/1.0",
        }

        payload: Dict[str, Any] = {
            "commit_id": head_sha,
            "body": summary_body,
            "event": "COMMENT",
            "comments": inline_comments[:15],  # Cap inline comments to avoid flooding
        }

        async def _send(c: httpx.AsyncClient) -> bool:
            try:
                res = await c.post(url, headers=headers, json=payload, timeout=20.0)
                if res.status_code in {200, 201}:
                    logger.info(f"Successfully posted review on {owner}/{repo} PR #{pr_number}")
                    return True
                elif res.status_code == 422:
                    logger.warning(
                        f"GitHub rejected review comments with 422 ({res.text}). "
                        "Retrying review body without inline comments..."
                    )
                    # Retry without inline comments
                    fallback_payload = {
                        "commit_id": head_sha,
                        "body": summary_body,
                        "event": "COMMENT",
                    }
                    fallback_res = await c.post(url, headers=headers, json=fallback_payload, timeout=15.0)
                    return fallback_res.status_code in {200, 201}
                else:
                    logger.error(f"Failed to post review: {res.status_code} - {res.text}")
                    return False
            except Exception as e:
                logger.error(f"Error posting review to GitHub: {e}")
                return False

        if client is not None:
            return await _send(client)
        else:
            async with httpx.AsyncClient(timeout=25.0) as default_client:
                return await _send(default_client)

    @classmethod
    async def execute_github_review_task(
        cls,
        review_run_id: int,
        repo_name: str,
        pr_number: int,
        head_sha: str,
        installation_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """
        Asynchronously executes full review pipeline for a GitHub PR webhook:
        1. Resolves installation token via GitHub App Auth
        2. Fetches PR diff and files
        3. Runs Tree-sitter AST and SAST security gates
        4. Maps findings to diff (inline vs out-of-diff) and checks deduplication
        5. Posts ONE atomic review to GitHub PR
        6. Updates ReviewRun and persists ReviewComment records in DB
        """
        t0 = time.time()
        _load_engine_packages()
        from context_engine import UnifiedDiffParser

        parts = repo_name.split("/")
        owner = parts[0] if len(parts) > 1 else "unknown"
        repo = parts[1] if len(parts) > 1 else repo_name

        async def _execute(db: AsyncSession):
            # 1. Fetch ReviewRun and PR from DB
            run = (
                await db.execute(select(ReviewRun).where(ReviewRun.id == review_run_id))
            ).scalars().first()
            if not run:
                logger.error(f"ReviewRun #{review_run_id} not found in DB.")
                return

            pr = (
                await db.execute(select(PullRequest).where(PullRequest.id == run.pr_id))
            ).scalars().first()

            # 2. Query previous comments for this PR to avoid duplicates on synchronize
            prev_comments = (
                await db.execute(
                    select(ReviewComment)
                    .join(ReviewRun, ReviewComment.review_run_id == ReviewRun.id)
                    .where(ReviewRun.pr_id == run.pr_id, ReviewRun.id != review_run_id)
                )
            ).scalars().all()
            existing_fingerprints = {
                (c.file_path, c.end_line, c.category) for c in prev_comments
            }

            # 3. Resolve installation token
            token: Optional[str] = None
            if installation_id:
                try:
                    token = await github_app_auth.get_installation_token(
                        installation_id, client=client
                    )
                except Exception as e:
                    logger.warning(f"Could not get GitHub App installation token: {e}")

            headers = {
                "User-Agent": "AICodeReviewer-Bot/1.0",
                "Accept": "application/vnd.github.v3+json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"

            # 4. Fetch PR diff and files
            pr_data, diff_text, files_dict = await PRScannerService._fetch_github_pr_bundle(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                headers=headers,
            )

            file_diffs = UnifiedDiffParser.parse(diff_text)

            # 5. Run AST & SAST security gates and LLM review
            # Create a scan request and run analysis
            from ..schemas.review import LiveScanRequest
            scan_req = LiveScanRequest(
                pr_url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
                github_token=token,
                post_to_github=False,  # We post using our review service below
                openai_api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
            )

            scan_resp = await PRScannerService.scan_pull_request(scan_req, db=db)
            findings = scan_resp.findings

            # 6. Map findings to diff and deduplicate
            inline_comments, out_of_diff = map_findings_to_diff(
                findings=findings,
                file_diffs=file_diffs,
                existing_fingerprints=existing_fingerprints,
            )

            summary_body = build_review_summary_body(
                head_sha=head_sha,
                total_findings=len(findings),
                inline_count=len(inline_comments),
                out_of_diff_findings=out_of_diff,
            )

            # 7. Post ONE review to GitHub
            if token:
                await cls.post_review(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    head_sha=head_sha,
                    inline_comments=inline_comments,
                    summary_body=summary_body,
                    token=token,
                    client=client,
                )

            # 8. Update ReviewRun and DB comments
            elapsed_ms = int((time.time() - t0) * 1000)
            run.status = "completed"
            run.latency_ms = elapsed_ms
            run.head_sha = head_sha
            if pr:
                pr.head_sha = head_sha

            for f in findings:
                comment = ReviewComment(
                    review_run_id=run.id,
                    file_path=f.file_path,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    category=f.category,
                    severity=f.severity,
                    confidence=f.confidence,
                    suggestion_body=(
                        f"{f.explanation}\n\n```suggestion\n{f.suggested_code}\n```"
                    ),
                    status=f.status,
                )
                db.add(comment)

            await db.commit()
            logger.info(f"ReviewRun #{review_run_id} completed successfully in {elapsed_ms}ms")

        if db_session is not None:
            await _execute(db_session)
        else:
            async with AsyncSessionLocal() as session:
                await _execute(session)

