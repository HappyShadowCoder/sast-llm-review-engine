import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.review_comment import ReviewComment
from ..schemas.webhook import NormalizedFeedbackEvent

logger = logging.getLogger(__name__)


class FeedbackHandler:
    @staticmethod
    async def process_feedback_event(
        session: AsyncSession,
        event: NormalizedFeedbackEvent,
    ) -> Optional[ReviewComment]:
        """
        Updates review_comments.status to 'accepted' or 'dismissed'
        based on VCS feedback events (reactions, thread resolution, commit suggestions).
        """
        if not event.external_comment_id:
            logger.info("Feedback event missing external_comment_id; skipping")
            return None

        # Look up by exact external_comment_id
        stmt = select(ReviewComment).where(
            ReviewComment.external_comment_id == str(event.external_comment_id)
        )
        result = await session.execute(stmt)
        comment = result.scalars().first()

        # If not found, look up by partial/suffix match (e.g. comment_gh_555 matching 555)
        if not comment:
            stmt_like = select(ReviewComment).where(
                ReviewComment.external_comment_id.ilike(f"%{event.external_comment_id}%")
            )
            res_like = await session.execute(stmt_like)
            comment = res_like.scalars().first()

        # If not found by external_comment_id, check if external_comment_id is our internal UUID
        if not comment:
            stmt_id = select(ReviewComment).where(ReviewComment.id == str(event.external_comment_id))
            res_id = await session.execute(stmt_id)
            comment = res_id.scalars().first()

        if not comment:
            logger.warning(
                f"Review comment with external_id/id {event.external_comment_id} not found in database"
            )
            return None

        old_status = comment.status
        comment.status = event.status
        await session.commit()
        await session.refresh(comment)
        logger.info(
            f"Updated ReviewComment {comment.id} status from '{old_status}' to '{comment.status}' (reason: {event.reason})"
        )
        return comment

    @staticmethod
    async def update_comment_status_direct(
        session: AsyncSession,
        comment_id: str,
        new_status: str,
    ) -> Optional[ReviewComment]:
        """Direct update by internal UUID."""
        stmt = select(ReviewComment).where(ReviewComment.id == comment_id)
        result = await session.execute(stmt)
        comment = result.scalars().first()

        if not comment:
            return None

        comment.status = new_status
        await session.flush()
        return comment
