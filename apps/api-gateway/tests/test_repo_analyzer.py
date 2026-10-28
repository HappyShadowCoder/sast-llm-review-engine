import pytest
from httpx import AsyncClient

from src.services.repo_analyzer import RepoAnalyzerService


def test_parse_git_url_valid_repo():
    owner, repo, pr = RepoAnalyzerService.parse_git_url("https://github.com/tiangolo/fastapi")
    assert owner == "tiangolo"
    assert repo == "fastapi"
    assert pr is None


def test_parse_git_url_with_git_extension():
    owner, repo, pr = RepoAnalyzerService.parse_git_url("https://github.com/pallets/flask.git")
    assert owner == "pallets"
    assert repo == "flask"
    assert pr is None


def test_parse_git_url_pull_request():
    owner, repo, pr = RepoAnalyzerService.parse_git_url("https://github.com/tiangolo/fastapi/pull/11000")
    assert owner == "tiangolo"
    assert repo == "fastapi"
    assert pr == 11000


def test_parse_git_url_invalid():
    with pytest.raises(ValueError):
        RepoAnalyzerService.parse_git_url("invalid-url-here")


@pytest.mark.asyncio
async def test_analyze_repo_endpoint_repository(client: AsyncClient):
    payload = {
        "git_url": "https://github.com/tiangolo/fastapi",
        "provider": "openai",
        "openai_api_key": None,
        "github_token": None,
        "model": "gpt-4o-mini",
    }
    res = await client.post("/api/v1/reviews/analyze-repo", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Validate high-level structure
    assert "repo_summary" in data
    assert data["repo_summary"]["owner"] == "tiangolo"
    assert data["repo_summary"]["name"] == "fastapi"
    assert 0 <= data["repo_summary"]["health_score"] <= 100
    assert "executive_summary" in data["repo_summary"]

    # Commits report
    assert "commits_report" in data
    assert len(data["commits_report"]) > 0
    c0 = data["commits_report"][0]
    assert "sha" in c0
    assert "message" in c0
    assert "risk_level" in c0

    # PRs report
    assert "prs_report" in data
    assert isinstance(data["prs_report"], list)

    # Code corrections
    assert "code_corrections" in data
    assert len(data["code_corrections"]) > 0
    corr = data["code_corrections"][0]
    assert "file_path" in corr
    assert "explanation" in corr
    assert "corrected_code" in corr
    assert corr["confidence"] >= 0.80

    # Architecture advice
    assert "architecture_advice" in data
    arch = data["architecture_advice"]
    assert "overall_critique" in arch
    assert "coupling_hotspots" in arch
    assert "scalability_bottlenecks" in arch

    # AST Insights
    assert "ast_insights" in data
    ast = data["ast_insights"]
    assert "total_symbols" in ast
    assert ast["total_symbols"] >= 0


@pytest.mark.asyncio
async def test_analyze_repo_endpoint_pull_request(client: AsyncClient):
    payload = {
        "git_url": "https://github.com/tiangolo/fastapi/pull/11000",
        "provider": "gemini",
        "gemini_api_key": None,
        "github_token": None,
    }
    res = await client.post("/api/v1/reviews/analyze-repo", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["repo_summary"]["target_type"] == "pull_request"
    assert "PR #11000" in data["repo_summary"]["analyzed_target"]


@pytest.mark.asyncio
async def test_analyze_repo_file_tree(client: AsyncClient):
    payload = {
        "git_url": "https://github.com/tiangolo/fastapi",
        "provider": "openai",
    }
    res = await client.post("/api/v1/reviews/analyze-repo", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "file_tree" in data
    assert isinstance(data["file_tree"], list)


@pytest.mark.asyncio
async def test_export_report_sarif_and_markdown(client: AsyncClient):
    # 1. Analyze repo
    payload = {
        "git_url": "https://github.com/tiangolo/fastapi",
        "provider": "openai",
    }
    res = await client.post("/api/v1/reviews/analyze-repo", json=payload)
    assert res.status_code == 200
    report_data = res.json()

    # 2. Test SARIF export
    sarif_res = await client.post(
        "/api/v1/reviews/export-report",
        json={"format": "sarif", "report": report_data},
    )
    assert sarif_res.status_code == 200
    sarif_body = sarif_res.json()
    assert sarif_body["content_type"] == "application/json"
    assert "sarif-schema-2.1.0" in sarif_body["content"]
    assert sarif_body["filename"].endswith(".sarif.json")

    # 3. Test Markdown export
    md_res = await client.post(
        "/api/v1/reviews/export-report",
        json={"format": "markdown", "report": report_data},
    )
    assert md_res.status_code == 200
    md_body = md_res.json()
    assert md_body["content_type"] == "text/markdown"
    assert "Security Audit Report" in md_body["content"]
    assert md_body["filename"].endswith(".md")

