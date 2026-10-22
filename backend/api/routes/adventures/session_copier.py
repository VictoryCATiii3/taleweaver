"""Duplicates an existing game session (avatar, state, chat, world, map and visuals)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.session_assets import (
    copy_data_asset_to_session,
    ensure_session_dir,
    rewrite_asset_snapshot_urls,
    rewrite_avatar_item_visual_urls,
)
from backend.api.routes.adventures.session_cloning import (
    clone_avatar,
    clone_entity,
    clone_exit,
    clone_scene,
)
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap
from backend.utils.text_utils import generate_session_id

_COPY_TITLE_PREFIX = "Kopie von "

# SessionState columns copied by value (JSON columns are deep-copied).
_STATE_VALUE_FIELDS = (
    "template_id",
    "current_scene_id",
    "in_game_time",
    "start_datetime",
    "time_system",
    "plot",
    "rules",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "tts_director_notes",
    "is_completed",
    "is_debug_enabled",
    "is_walkthrough_revealed",
    "allow_dynamic_items",
)
_STATE_JSON_FIELDS = (
    "time_config",
    "inventory",
    "exit_states",
    "discovered_scenes",
    "quests",
    "selected_image_styles",
    "selected_tone",
)


async def _first(db: AsyncSession, statement: Any) -> Any:
    return (await db.execute(statement)).scalars().first()


async def _session_rows(db: AsyncSession, model: Any, session_id: str) -> list[Any]:
    result = await db.execute(select(model).where(model.session_id == session_id))
    return list(result.scalars().all())


def _copy_title(original_title: Optional[str]) -> str:
    title = original_title or "Unknown Adventure"
    return title if title.startswith(_COPY_TITLE_PREFIX) else f"{_COPY_TITLE_PREFIX}{title}"


def _copied_entity_states(state: SessionState, session_id: str, asset_cache: dict[str, str]) -> Any:
    entity_states = deepcopy(state.entity_states)
    if not isinstance(entity_states, dict):
        return entity_states
    snapshot = entity_states.get("__asset_snapshot__")
    if isinstance(snapshot, dict):
        entity_states["__asset_snapshot__"] = rewrite_asset_snapshot_urls(
            session_id, snapshot, asset_cache
        )
    return entity_states


def _clone_state(
    state: SessionState,
    session_id: str,
    user_id: str,
    avatar_id: str,
    asset_cache: dict[str, str],
) -> SessionState:
    return SessionState(
        session_id=session_id,
        user_id=user_id,
        avatar_id=avatar_id,
        max_memory_turns=getattr(state, "max_memory_turns", 10) or 10,
        entity_states=_copied_entity_states(state, session_id, asset_cache),
        **{field: getattr(state, field) for field in _STATE_VALUE_FIELDS},
        **{field: deepcopy(getattr(state, field)) for field in _STATE_JSON_FIELDS},
    )


async def _clone_world(
    db: AsyncSession, source_id: str, session_id: str, asset_cache: dict[str, str]
) -> None:
    for msg in await _session_rows(db, ChatMessage, source_id):
        db.add(ChatMessage(session_id=session_id, role=msg.role, content=msg.content))

    for scene in await _session_rows(db, WorldScene, source_id):
        image = copy_data_asset_to_session(session_id, "scenes", scene.image_url, asset_cache)
        db.add(clone_scene(scene, session_id, image))

    for exit_row in await _session_rows(db, WorldExit, source_id):
        db.add(clone_exit(exit_row, session_id))

    for ent in await _session_rows(db, WorldEntity, source_id):
        image = copy_data_asset_to_session(session_id, "entities", ent.image_url, asset_cache)
        db.add(
            clone_entity(
                ent,
                session_id,
                image,
                is_in_inventory=ent.is_in_inventory,
                unlock_rule=None,
                voice=ent.voice,
            )
        )

    original_map = await _first(db, select(WorldMap).where(WorldMap.session_id == source_id))
    if original_map:
        db.add(
            WorldMap(
                template_id=original_map.template_id,
                session_id=session_id,
                nodes=deepcopy(original_map.nodes),
                edges=deepcopy(original_map.edges),
                current_scene_id=original_map.current_scene_id,
            )
        )


async def copy_session(db: AsyncSession, game_id: str, user: User) -> dict[str, Any]:
    """Creates a full duplicate of the user's session ``game_id`` (commits)."""
    original = await _first(
        db,
        select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == user.id)),
    )
    if not original:
        raise HTTPException(status_code=404, detail="Session not found.")
    original_avatar = await _first(db, select(Avatar).where(Avatar.id == original.avatar_id))
    if not original_avatar:
        raise HTTPException(status_code=404, detail="Session avatar not found.")

    cloned_avatar = clone_avatar(original_avatar, user.id, original_avatar.template_id)
    db.add(cloned_avatar)
    await db.flush()

    copied = GameSession(
        id=generate_session_id(original.adventure_title or original.template_id or "copy"),
        user_id=user.id,
        avatar_id=cloned_avatar.id,
        template_id=original.template_id,
        adventure_title=_copy_title(original.adventure_title),
        adventure_image_url=original.adventure_image_url,
        status=original.status,
        status_note=original.status_note,
        copied_from_id=original.id,
    )
    db.add(copied)
    await db.flush()
    ensure_session_dir(copied.id)

    asset_cache: dict[str, str] = {}
    copied.adventure_image_url = (
        copy_data_asset_to_session(copied.id, "cover", original.adventure_image_url, asset_cache)
        or original.adventure_image_url
    )
    cloned_avatar.profile_image = (
        copy_data_asset_to_session(
            copied.id, "protagonist", original_avatar.profile_image, asset_cache
        )
        or original_avatar.profile_image
    )
    rewrite_avatar_item_visual_urls(cloned_avatar, copied.id, asset_cache)

    original_state = await _first(
        db, select(SessionState).where(SessionState.session_id == original.id)
    )
    if original_state:
        db.add(_clone_state(original_state, copied.id, user.id, cloned_avatar.id, asset_cache))

    await _clone_world(db, original.id, copied.id, asset_cache)
    await db.commit()
    return {"game_id": copied.id, "template_id": copied.template_id, "avatar_id": cloned_avatar.id}
