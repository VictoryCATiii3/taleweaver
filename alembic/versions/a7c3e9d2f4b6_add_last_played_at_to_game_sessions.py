"""Add last_played_at to game_sessions

Revision ID: a7c3e9d2f4b6
Revises: e6a2c4f8b1d9
Create Date: 2026-10-24 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9d2f4b6"
down_revision = "e6a2c4f8b1d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("game_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_played_at", sa.DateTime(timezone=True), nullable=True))

    # Best available proxy for existing sessions: the last time their state was written.
    op.execute(
        """
        UPDATE game_sessions
        SET last_played_at = COALESCE(
            (SELECT MAX(session_states.updated_at)
             FROM session_states
             WHERE session_states.session_id = game_sessions.id),
            game_sessions.created_at
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("game_sessions", schema=None) as batch_op:
        batch_op.drop_column("last_played_at")
