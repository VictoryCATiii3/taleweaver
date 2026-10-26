"""add setup_wizard to users

Revision ID: f2b6d8a4c1e9
Revises: e7a1c4d9b2f6
Create Date: 2026-10-26 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b6d8a4c1e9"
down_revision: Union[str, Sequence[str], None] = "e7a1c4d9b2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("setup_wizard", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("setup_wizard")
