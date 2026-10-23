"""reset legacy adventure origin_ids

``origin_id`` is now a system-generated stable adventure identity (UUID). Existing values
are not usable as identity: they are empty strings, LLM-generated starting-scene IDs
(shared between an adventure and its covers) or template-ID fallbacks that no export ever
carried. They are reset to NULL so these templates fall back to title matching until their
next update or export assigns a real ID.

Revision ID: e6a2c4f8b1d9
Revises: d3f8a1b6c2e4
Create Date: 2026-10-23 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6a2c4f8b1d9"
down_revision = "d3f8a1b6c2e4"
branch_labels = None
depends_on = None

_templates = sa.table("adventure_templates", sa.column("origin_id", sa.String))


def upgrade() -> None:
    op.execute(_templates.update().values(origin_id=None))


def downgrade() -> None:
    # Data-only migration: the discarded legacy values cannot be restored.
    pass
