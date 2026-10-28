from typing import Optional
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, generate_uuid


class ReviewComment(Base, TimestampMixin):
    __tablename__ = "review_comments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    review_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_comment_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    end_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,  # 'architecture' | 'security' | 'performance' | 'concurrency' | 'bug'
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,  # 'critical' | 'high' | 'medium'
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    suggestion_body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,  # 'pending' | 'accepted' | 'dismissed'
    )

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship(
        "ReviewRun",
        back_populates="comments",
    )

    __table_args__ = (
        Index("idx_review_comments_run_id", "review_run_id"),
        Index("idx_review_comments_ext_id", "external_comment_id"),
        Index("idx_review_comments_status", "status"),
        Index("idx_review_comments_category", "category"),
    )
