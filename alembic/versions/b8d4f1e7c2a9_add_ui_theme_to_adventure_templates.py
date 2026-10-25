"""add ui_theme to adventure templates

Revision ID: b8d4f1e7c2a9
Revises: a7c3e9d2f4b6
Create Date: 2026-10-25 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4f1e7c2a9"
down_revision: Union[str, Sequence[str], None] = "a7c3e9d2f4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ui_theme", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("ui_theme")
