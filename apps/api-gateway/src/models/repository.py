from typing import List, Optional
from sqlalchemy import Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, generate_uuid


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    vcs_provider: Mapped[str] = mapped_column(
        String(16),
        nullable=False,  # 'github' | 'gitlab'
    )
    external_repo_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    default_branch: Mapped[str] = mapped_column(
        String(128),
        default="main",
        nullable=False,
    )
    installation_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # Relationships
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_repositories_provider_ext_id", "vcs_provider", "external_repo_id", unique=True),
        Index("idx_repositories_name", "name"),
    )
