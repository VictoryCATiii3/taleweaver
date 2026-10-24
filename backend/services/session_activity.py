"""Tracks when a player last opened a game session."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import utc_now
from backend.models.game_session import GameSession


async def mark_session_played(db: AsyncSession, session_id: str) -> None:
    """Stamps the session as just played so the portal can surface it as the latest journey."""
    await db.execute(
        update(GameSession).where(GameSession.id == session_id).values(last_played_at=utc_now())
    )
    await db.commit()
