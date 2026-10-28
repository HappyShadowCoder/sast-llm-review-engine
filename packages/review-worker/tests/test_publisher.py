from src.models import ReviewFinding
from src.publisher import VCSPublisher


def test_anti_noise_confidence_filtering(publisher: VCSPublisher):
    findings = [
        # High confidence -> must PASS
        ReviewFinding(
            file_path="src/auth.py",
            start_line=10,
            end_line=12,
            category="security",
            severity="critical",
            confidence=0.95,
            explanation="Critical auth bypass.",
            suggested_code="return verify(token)",
        ),
        # Low confidence (< 0.80) -> must be DROPPED
        ReviewFinding(
            file_path="src/utils.py",
            start_line=20,
            end_line=22,
            category="performance",
            severity="medium",
            confidence=0.74,
            explanation="Uncertain performance complaint.",
            suggested_code="pass",
        ),
        # Style nitpick -> must be DROPPED
        ReviewFinding(
            file_path="src/main.py",
            start_line=5,
            end_line=6,
            category="style_nitpick",
            severity="low",
            confidence=0.99,
            explanation="Variable naming style.",
            suggested_code="x = 1",
        ),
    ]

    filtered = publisher.filter_and_deduplicate(findings, min_confidence=0.80)
    assert len(filtered) == 1
    assert filtered[0].file_path == "src/auth.py"
    assert filtered[0].confidence == 0.95


def test_anti_noise_overlapping_deduplication(publisher: VCSPublisher):
    # Two findings covering overlapping lines in the same file
    f_lower = ReviewFinding(
        file_path="src/db.py",
        start_line=15,
        end_line=20,
        category="bug",
        severity="medium",
        confidence=0.82,
        explanation="Lower confidence report",
        suggested_code="pass",
    )
    f_higher = ReviewFinding(
        file_path="src/db.py",
        start_line=16,
        end_line=18,
        category="security",
        severity="critical",
        confidence=0.96,
        explanation="Higher confidence SQL injection fix",
        suggested_code="cursor.execute(%s)",
    )

    deduped = publisher.filter_and_deduplicate([f_lower, f_higher])
    assert len(deduped) == 1
    # Higher confidence finding must win
    assert deduped[0].confidence == 0.96
    assert deduped[0].category == "security"


def test_github_suggestion_formatting(publisher: VCSPublisher):
    finding = ReviewFinding(
        file_path="src/query.py",
        start_line=10,
        end_line=12,
        category="security",
        severity="critical",
        confidence=0.97,
        explanation="Fix SQL injection vulnerability.",
        suggested_code="SELECT * FROM accounts WHERE id = :id",
    )

    formatted = publisher.format_github_suggestion(finding)
    assert "```suggestion" in formatted
    assert "SELECT * FROM accounts WHERE id = :id" in formatted
    assert "```" in formatted
    assert "[CRITICAL] Category: `Security`" in formatted
    assert "Confidence: 97%" in formatted


def test_gitlab_suggestion_formatting(publisher: VCSPublisher):
    finding = ReviewFinding(
        file_path="src/query.py",
        start_line=10,
        end_line=12,
        category="performance",
        severity="high",
        confidence=0.89,
        explanation="Add index lookup.",
        suggested_code="account = get_cached_account(id)",
    )

    formatted = publisher.format_gitlab_suggestion(finding)
    assert "```suggestion:-0+0" in formatted
    assert "account = get_cached_account(id)" in formatted
    assert "```" in formatted


def test_publish_github_review_simulation(publisher: VCSPublisher):
    findings = [
        ReviewFinding(
            file_path="src/service.py",
            start_line=5,
            end_line=7,
            category="concurrency",
            severity="high",
            confidence=0.91,
            explanation="Acquire lock before writing to shared state.",
            suggested_code="with self.lock:\n    self.state = new_state",
        )
    ]

    result = publisher.publish_github_review(
        repo_owner_name="org/repo",
        pull_number=14,
        head_sha="sha999",
        summary="Concurrency issue resolved.",
        findings=findings,
    )

    assert result["status"] == "published_simulated"
    assert result["comments_count"] == 1
    assert len(result["external_comment_ids"]) == 1
