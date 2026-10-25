"""add lookup indexes for sessions, world data and chat history

Foreign-key style columns (session_id, template_id, user_id, owner_id) had no indexes, so
SQLite scanned whole tables or built temporary indexes for every lookup.

Revision ID: c3e7a9d1f5b2
Revises: b8d4f1e7c2a9
Create Date: 2026-10-25 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e7a9d1f5b2"
down_revision: Union[str, Sequence[str], None] = "b8d4f1e7c2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_world_scenes_session_id_id", "world_scenes", ("session_id", "id")),
    ("ix_world_scenes_template_id_id", "world_scenes", ("template_id", "id")),
    ("ix_world_exits_session_id_from_scene_id", "world_exits", ("session_id", "from_scene_id")),
    ("ix_world_exits_template_id_from_scene_id", "world_exits", ("template_id", "from_scene_id")),
    ("ix_world_entities_session_id_id", "world_entities", ("session_id", "id")),
    ("ix_world_entities_template_id_id", "world_entities", ("template_id", "id")),
    ("ix_game_sessions_user_id_status", "game_sessions", ("user_id", "status")),
    ("ix_game_sessions_template_id", "game_sessions", ("template_id",)),
    ("ix_session_states_session_id", "session_states", ("session_id",)),
    ("ix_session_states_template_id", "session_states", ("template_id",)),
    ("ix_chat_messages_session_id_created_at", "chat_messages", ("session_id", "created_at")),
    ("ix_avatars_template_id", "avatars", ("template_id",)),
    ("ix_avatars_user_id", "avatars", ("user_id",)),
    ("ix_adventure_templates_owner_id", "adventure_templates", ("owner_id",)),
    (
        "ix_session_checkpoints_session_id_created_at",
        "session_checkpoints",
        ("session_id", "created_at"),
    ),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, list(columns), if_not_exists=True)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
