"""Initial schema: repositories, pull_requests, review_runs, review_comments

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("vcs_provider", sa.String(length=16), nullable=False),
        sa.Column("external_repo_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=128), nullable=False, server_default="main"),
        sa.Column("installation_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_repositories_provider_ext_id",
        "repositories",
        ["vcs_provider", "external_repo_id"],
        unique=True,
    )
    op.create_index("idx_repositories_name", "repositories", ["name"])

    # 2. pull_requests table
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("repo_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_pull_requests_repo_pr_num",
        "pull_requests",
        ["repo_id", "pr_number"],
        unique=True,
    )
    op.create_index("idx_pull_requests_head_sha", "pull_requests", ["head_sha"])

    # 3. review_runs table
    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pr_id", sa.String(length=36), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_review_runs_pr_id", "review_runs", ["pr_id"])
    op.create_index("idx_review_runs_status", "review_runs", ["status"])

    # 4. review_comments table
    op.create_table(
        "review_comments",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("review_run_id", sa.String(length=36), sa.ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_comment_id", sa.String(length=128), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("suggestion_body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_review_comments_run_id", "review_comments", ["review_run_id"])
    op.create_index("idx_review_comments_ext_id", "review_comments", ["external_comment_id"])
    op.create_index("idx_review_comments_status", "review_comments", ["status"])
    op.create_index("idx_review_comments_category", "review_comments", ["category"])


def downgrade() -> None:
    op.drop_table("review_comments")
    op.drop_table("review_runs")
    op.drop_table("pull_requests")
    op.drop_table("repositories")
