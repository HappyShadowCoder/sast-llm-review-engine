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

    # Code corrections (0 for clean production codebases like FastAPI, or list of findings)
    assert "code_corrections" in data
    assert isinstance(data["code_corrections"], list)
    if len(data["code_corrections"]) > 0:
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


def test_dynamic_mermaid_diagram_synthesis():
    """Validates dynamic, non-hardcoded GitDiagram generation across repository types."""
    from services.repo_analyzer import RepoAnalyzerService

    # 1. Static Site Generator (e.g. mapc-site)
    mapc_files = {
        "index.html": "<html>Landing</html>",
        "changelog.html": "<html>Releases</html>",
        "wall.html": "<html>Wall of Fame</html>",
        "site.js": "fetch('/supporters.json')",
        "supporters.json": '{"supporters": []}',
        "build.py": "def build(): pass",
        "downloads.json": '{"releases": []}',
    }
    mapc_diag = RepoAnalyzerService._generate_system_mermaid_diagram(
        owner="abduzeedo",
        repo="mapc-site",
        source_files=mapc_files,
        all_symbols=[],
        dependency_map=[{"source": "site.js", "target": "supporters.json", "type": "fetch"}],
        coupling_hotspots=[],
    )
    assert "Web Pages & Views" in mapc_diag
    assert "Client Scripts & Components" in mapc_diag
    assert "Data Feeds & Config" in mapc_diag
    assert "Build Automation" in mapc_diag
    assert "apps/dashboard" not in mapc_diag

    # 2. Monorepo (e.g. sast-llm-review-engine)
    monorepo_files = {
        "apps/dashboard/src/app/page.tsx": "export default function Home() {}",
        "apps/api-gateway/src/main.py": "from fastapi import FastAPI; app = FastAPI()",
        "packages/context-engine/src/analyzer.py": "class TreeSitterAnalyzer: pass",
        "packages/review-worker/src/runner.py": "class SASTRunner: pass",
        "packages/ml-pipeline/src/train.py": "def train(): pass",
    }
    mono_diag = RepoAnalyzerService._generate_system_mermaid_diagram(
        owner="HappyShadowCoder",
        repo="sast-llm-review-engine",
        source_files=monorepo_files,
        all_symbols=[],
        dependency_map=[
            {"source": "apps/api-gateway/src/main.py", "target": "packages/context-engine/src/analyzer.py", "type": "import"}
        ],
        coupling_hotspots=[],
    )
    assert "apps/dashboard" in mono_diag
    assert "apps/api-gateway" in mono_diag
    assert "packages/context-engine" in mono_diag
    assert "packages/review-worker" in mono_diag
    assert "packages/ml-pipeline" in mono_diag
    assert "DirectX" not in mono_diag
    assert "Wall of Fame" not in mono_diag

    # 3. Generic Backend Microservice
    generic_files = {
        "api/routes.py": "def route(): pass",
        "services/user_service.py": "def get_user(): pass",
        "models/user.py": "class User: pass",
        "workers/task_queue.py": "def process_task(): pass",
    }
    generic_diag = RepoAnalyzerService._generate_system_mermaid_diagram(
        owner="test-org",
        repo="backend-api",
        source_files=generic_files,
        all_symbols=[],
        dependency_map=[
            {"source": "api/routes.py", "target": "services/user_service.py", "type": "import"},
            {"source": "services/user_service.py", "target": "models/user.py", "type": "import"},
        ],
        coupling_hotspots=[],
    )
    assert "api" in generic_diag
    assert "services" in generic_diag
    assert "models" in generic_diag
    assert "workers" in generic_diag
    assert "DirectX" not in generic_diag
    assert "apps/dashboard" not in generic_diag



