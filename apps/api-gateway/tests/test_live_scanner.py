import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import PullRequest, Repository, ReviewComment


@pytest.mark.asyncio
async def test_scan_github_pr_endpoint(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "pr_url": "https://github.com/tiangolo/fastapi/pull/11000",
        "github_token": None,
        "post_to_github": False,
    }

    res = await client.post("/api/v1/reviews/scan-github-pr", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "pr_title" in data
    assert "repository" in data
    assert data["repository"] == "tiangolo/fastapi"
    assert "files_scanned" in data
    assert len(data["files_scanned"]) > 0
    assert "findings" in data
    assert data["total_findings"] >= 1

    # Verify that the first finding conforms to schema
    finding = data["findings"][0]
    assert "category" in finding
    assert "severity" in finding
    assert "confidence" in finding
    assert finding["confidence"] >= 0.80  # anti-noise gate
    assert "suggested_code" in finding
    assert "explanation" in finding

    # Verify database persistence
    repo_stmt = select(Repository).where(Repository.name == "tiangolo/fastapi")
    repo = (await db_session.execute(repo_stmt)).scalars().first()
    assert repo is not None

    pr_stmt = select(PullRequest).where(PullRequest.repo_id == repo.id)
    prs = (await db_session.execute(pr_stmt)).scalars().all()
    assert len(prs) >= 1

    comments_stmt = select(ReviewComment)
    comments = (await db_session.execute(comments_stmt)).scalars().all()
    assert len(comments) >= 1


@pytest.mark.asyncio
async def test_scan_github_repo_url(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "pr_url": "https://github.com/pallets/flask",
        "github_token": None,
        "post_to_github": False,
    }

    res = await client.post("/api/v1/reviews/scan-github-pr", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["repository"] == "pallets/flask"
    assert len(data["files_scanned"]) > 0


@pytest.mark.asyncio
async def test_scan_github_invalid_url(client: AsyncClient):
    payload = {
        "pr_url": "not-a-valid-github-url",
        "github_token": None,
        "post_to_github": False,
    }

    res = await client.post("/api/v1/reviews/scan-github-pr", json=payload)
    assert res.status_code == 400
    assert "Invalid GitHub URL format" in res.json()["detail"]


@pytest.mark.asyncio
async def test_scan_github_zero_pr_repo(client: AsyncClient):
    payload = {
        "pr_url": "https://github.com/HappyShadowCoder/Travel-Itinerary.git",
        "github_token": None,
        "post_to_github": False,
    }

    res = await client.post("/api/v1/reviews/scan-github-pr", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["repository"] == "HappyShadowCoder/Travel-Itinerary"
    assert len(data["files_scanned"]) > 0
    assert data["total_findings"] >= 0
