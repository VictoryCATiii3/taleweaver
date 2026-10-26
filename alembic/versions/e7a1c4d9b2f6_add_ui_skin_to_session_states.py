"""add ui_skin to session states

Revision ID: e7a1c4d9b2f6
Revises: d4f8b2e6a1c3
Create Date: 2026-10-26 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a1c4d9b2f6"
down_revision: Union[str, Sequence[str], None] = "d4f8b2e6a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ui_skin", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.drop_column("ui_skin")
