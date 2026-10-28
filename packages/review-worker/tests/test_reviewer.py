import json
import pytest
from pydantic import ValidationError

from src.models import ReviewFinding, ReviewResponse, SASTFinding
from src.reviewer import StructuredReviewer


def test_review_finding_schema_validation():
    # Valid finding
    finding = ReviewFinding(
        file_path="src/auth.py",
        start_line=10,
        end_line=15,
        category="security",
        severity="critical",
        confidence=0.95,
        explanation="SQL injection detected in cursor.execute call.",
        suggested_code="cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
    )
    assert finding.confidence == 0.95
    assert finding.is_noise() is False


def test_review_finding_invalid_range_raises_error():
    # end_line < start_line
    with pytest.raises(ValidationError):
        ReviewFinding(
            file_path="src/auth.py",
            start_line=20,
            end_line=15,
            category="bug",
            severity="high",
            confidence=0.9,
            explanation="Invalid lines",
            suggested_code="pass",
        )


def test_review_finding_invalid_confidence_raises_error():
    # confidence > 1.0
    with pytest.raises(ValidationError):
        ReviewFinding(
            file_path="src/auth.py",
            start_line=10,
            end_line=12,
            category="architecture",
            severity="medium",
            confidence=1.5,
            explanation="Out of bounds",
            suggested_code="pass",
        )


def test_structured_reviewer_mock_execution(reviewer: StructuredReviewer):
    mock_llm_json = json.dumps({
        "summary": "Detected critical SQL injection in user query handler.",
        "findings": [
            {
                "file_path": "src/api/users.py",
                "start_line": 25,
                "end_line": 30,
                "category": "security",
                "severity": "critical",
                "confidence": 0.98,
                "explanation": "User supplied input is concatenated directly into SQL statement.",
                "suggested_code": "cursor.execute('SELECT * FROM users WHERE name = %s', (username,))",
            }
        ]
    })

    sast_finding = SASTFinding(
        rule_id="security.sqli",
        file_path="src/api/users.py",
        start_line=25,
        end_line=30,
        message="SQL injection",
        severity="critical",
        snippet="cursor.execute(f'SELECT * FROM users WHERE name = {username}')",
    )

    response = reviewer.review_pr(
        pr_title="Add user query endpoint",
        formatted_ast_context="def get_users(): ...",
        sast_findings=[sast_finding],
        mock_response=mock_llm_json,
    )

    assert isinstance(response, ReviewResponse)
    assert len(response.findings) == 1
    f = response.findings[0]
    assert f.file_path == "src/api/users.py"
    assert f.category == "security"
    assert f.confidence >= 0.80
    assert "suggested_code" in f.model_dump()
