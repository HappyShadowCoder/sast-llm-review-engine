from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, generate_uuid, utc_now


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    repo_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    pr_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    author: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    head_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    base_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="open",
        nullable=False,  # 'open' | 'closed' | 'merged'
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="pull_requests",
    )
    review_runs: Mapped[List["ReviewRun"]] = relationship(
        "ReviewRun",
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_pull_requests_repo_pr_num", "repo_id", "pr_number", unique=True),
        Index("idx_pull_requests_head_sha", "head_sha"),
    )
