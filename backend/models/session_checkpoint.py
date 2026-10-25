import uuid6
from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base, TimestampMixin


class SessionCheckpoint(Base, TimestampMixin):
    __tablename__ = "session_checkpoints"
    __table_args__ = (
        Index("ix_session_checkpoints_session_id_created_at", "session_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    session_id = Column(
        String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_index = Column(Integer, nullable=False)
    state_snapshot = Column(JSON, nullable=False)
    trigger_reason = Column(String(64), nullable=False)

    session = relationship("GameSession", back_populates="checkpoints")
