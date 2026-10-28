import asyncio
from datetime import datetime, timedelta, timezone
import random
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PullRequest, Repository, ReviewComment, ReviewRun
from ..database import AsyncSessionLocal, engine, Base


async def seed_telemetry_data(session: AsyncSession) -> int:
    """
    Seeds realistic 90-day engineering telemetry across core tables.
    Returns the number of seeded review comments.
    """
    # Check if already seeded
    existing_repo = (await session.execute(select(Repository))).scalars().first()
    if existing_repo:
        count = (await session.execute(select(ReviewComment))).scalars().all()
        return len(count)

    now = datetime.now(timezone.utc)

    # 1. Repositories
    repo_gh = Repository(
        vcs_provider="github",
        external_repo_id="100991",
        name="acme/cloud-payment-service",
        default_branch="main",
        installation_id="inst_991",
    )
    repo_gl = Repository(
        vcs_provider="gitlab",
        external_repo_id="200882",
        name="acme/identity-auth-engine",
        default_branch="main",
    )
    session.add_all([repo_gh, repo_gl])
    await session.flush()

    repos = [repo_gh, repo_gl]
    categories = ["security", "architecture", "concurrency", "performance", "bug"]
    severities = ["critical", "high", "medium"]

    sample_files = [
        "src/auth/jwt_validator.py",
        "src/payments/ledger.py",
        "src/routes/checkout.py",
        "src/db/connection_pool.py",
        "src/concurrency/distributed_lock.py",
        "src/services/order_service.py",
    ]

    total_comments = 0

    # 2. Generate 90 days of PRs (12 weeks, ~3 PRs per week)
    for day_offset in range(90, 0, -2):
        created_time = now - timedelta(days=day_offset, hours=random.randint(1, 12))
        repo = random.choice(repos)
        pr_num = 100 + (90 - day_offset)

        pr = PullRequest(
            repo_id=repo.id,
            pr_number=pr_num,
            title=f"Feature {pr_num}: Update module {random.choice(sample_files).split('/')[-1].replace('.py', '')}",
            author=random.choice(["alice", "bob", "carol", "dave", "elena"]),
            head_sha=f"sha_{day_offset}_{random.randint(1000, 9999)}",
            base_sha="base_main_sha",
            status="merged" if day_offset > 3 else "open",
            opened_at=created_time,
            merged_at=created_time + timedelta(hours=random.randint(2, 48)) if day_offset > 3 else None,
        )
        session.add(pr)
        await session.flush()

        run = ReviewRun(
            pr_id=pr.id,
            head_sha=pr.head_sha,
            status="completed",
            latency_ms=random.randint(1400, 4200),
            tokens_used=random.randint(850, 3200),
            created_at=created_time + timedelta(minutes=random.randint(2, 6)),
            completed_at=created_time + timedelta(minutes=random.randint(3, 7)),
        )
        session.add(run)
        await session.flush()

        # Older comments had lower acceptance rate (~45%), newer comments (post-DPO) have high acceptance (~85%)
        acceptance_prob = 0.45 if day_offset > 60 else (0.70 if day_offset > 30 else 0.88)
        num_comments = random.randint(1, 3)

        for c_idx in range(num_comments):
            target_file = random.choice(sample_files)
            cat = random.choice(categories)
            sev = random.choice(severities)
            is_accepted = random.random() < acceptance_prob
            comm_status = "accepted" if is_accepted else ("dismissed" if random.random() < 0.8 else "pending")

            comment = ReviewComment(
                review_run_id=run.id,
                external_comment_id=f"gh_comm_{run.id[:8]}_{c_idx}",
                file_path=target_file,
                start_line=random.randint(10, 45),
                end_line=random.randint(46, 75),
                category=cat,
                severity=sev,
                confidence=round(random.uniform(0.82, 0.99), 2),
                suggestion_body=f"# Remediate {cat} issue\ndef optimized_call():\n    return safe_execute()",
                status=comm_status,
                created_at=run.created_at,
                updated_at=run.created_at + timedelta(hours=random.randint(1, 10)),
            )
            session.add(comment)
            total_comments += 1

    await session.commit()
    return total_comments


async def run_standalone_seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        count = await seed_telemetry_data(session)
        print(f"Database seeded with {count} comments across 90 days.")


if __name__ == "__main__":
    asyncio.run(run_standalone_seed())
