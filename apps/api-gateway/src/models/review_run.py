from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import generate_uuid, utc_now


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    pr_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    head_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,  # 'pending' | 'in_progress' | 'completed' | 'failed'
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship(
        "PullRequest",
        back_populates="review_runs",
    )
    comments: Mapped[List["ReviewComment"]] = relationship(
        "ReviewComment",
        back_populates="review_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_review_runs_pr_id", "pr_id"),
        Index("idx_review_runs_status", "status"),
    )
