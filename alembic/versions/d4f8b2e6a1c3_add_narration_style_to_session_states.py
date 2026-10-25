"""add narration_style to session states

Revision ID: d4f8b2e6a1c3
Revises: c3e7a9d1f5b2
Create Date: 2026-10-25 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8b2e6a1c3"
down_revision: Union[str, Sequence[str], None] = "c3e7a9d1f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "narration_style",
                sa.String(length=16),
                nullable=False,
                server_default="balanced",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.drop_column("narration_style")
