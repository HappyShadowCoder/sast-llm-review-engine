import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.seed_demo_data import seed_telemetry_data


@pytest.mark.asyncio
async def test_analytics_overview_empty_and_seeded(client: AsyncClient, db_session: AsyncSession):
    # 1. Test endpoint with empty DB (returns safe baseline)
    res_empty = await client.get("/api/v1/analytics/overview")
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["suggestion_acceptance_rate"] > 0
    assert "pre_merge_catch_rate" in data_empty
    assert "noise_suppression_ratio" in data_empty

    # 2. Seed data
    await seed_telemetry_data(db_session)

    # 3. Test endpoint with populated database
    res = await client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total_findings_caught"] > 0
    assert data["total_prs_reviewed"] > 0
    assert data["suggestion_acceptance_rate"] >= 0.0


@pytest.mark.asyncio
async def test_analytics_trends_endpoint(client: AsyncClient, db_session: AsyncSession):
    await seed_telemetry_data(db_session)

    res = await client.get("/api/v1/analytics/trends")
    assert res.status_code == 200
    data = res.json()

    assert "weekly_defects" in data
    assert len(data["weekly_defects"]) == 12
    assert "model_checkpoints" in data
    assert len(data["model_checkpoints"]) == 3

    # Check model checkpoint milestone progression
    checkpoints = data["model_checkpoints"]
    assert checkpoints[0]["name"].startswith("Base Model")
    assert checkpoints[1]["name"].startswith("SFT QLoRA")
    assert checkpoints[2]["name"].startswith("DPO Aligned")
    assert checkpoints[2]["acceptance_rate"] > checkpoints[0]["acceptance_rate"]


@pytest.mark.asyncio
async def test_analytics_hotspots_endpoint(client: AsyncClient, db_session: AsyncSession):
    await seed_telemetry_data(db_session)

    res = await client.get("/api/v1/analytics/hotspots")
    assert res.status_code == 200
    hotspots = res.json()
    assert len(hotspots) > 0

    first = hotspots[0]
    assert "file_path" in first
    assert "risk_score" in first
    assert "dominant_category" in first
    assert len(first["recurring_anti_patterns"]) > 0


@pytest.mark.asyncio
async def test_analytics_reviews_endpoint(client: AsyncClient, db_session: AsyncSession):
    await seed_telemetry_data(db_session)

    res = await client.get("/api/v1/analytics/reviews")
    assert res.status_code == 200
    reviews = res.json()
    assert len(reviews) > 0

    rev = reviews[0]
    assert "pr_number" in rev
    assert "file_path" in rev
    assert "diff_snippet" in rev
    assert "ast_context" in rev
    assert "suggested_code" in rev
    assert "confidence" in rev
    assert rev["status"] in {"pending", "accepted", "dismissed"}
