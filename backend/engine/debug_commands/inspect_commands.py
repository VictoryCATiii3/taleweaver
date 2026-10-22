"""Read-only ``/debug`` sub-commands that report session and world state."""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from backend.core.config import settings
from backend.engine.debug_commands.context import (
    DebugContext,
    entity_with_overrides,
    position_suffix,
    session_entities,
    session_scene_labels,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


async def _current_scene(ctx: DebugContext) -> Optional[WorldScene]:
    res = await ctx.db.execute(
        select(WorldScene).where(
            WorldScene.id == ctx.state.scene_id, WorldScene.session_id == ctx.state.session_id
        )
    )
    return res.scalars().first()


async def scene_info(ctx: DebugContext) -> str:
    scene_id = ctx.state.scene_id
    scene = await _current_scene(ctx)
    if not scene:
        return f"DEBUG ERROR: Scene '{scene_id}' not found in session manifest."
    return (
        f"--- DEBUG: SCENE [{scene_id}] ---\nLabel: {scene.label}\nDescription: {scene.description}"
    )


async def scene_entities(ctx: DebugContext) -> str:
    scene_id = ctx.state.scene_id
    res = await ctx.db.execute(
        select(WorldEntity).where(
            WorldEntity.current_scene_id == scene_id,
            WorldEntity.session_id == ctx.state.session_id,
        )
    )
    overrides = ctx.state.entity_states or {}
    processed = [entity_with_overrides(e, overrides) for e in res.scalars().all()]
    if not processed:
        return "--- DEBUG: No entities or objects found in this scene. ---"

    lines = [f"--- DEBUG: ENTITIES IN {scene_id} ---"]
    for e in processed:
        pos = position_suffix(e, " @ {}")
        description = str(e.get("description", ""))[:50]
        lines.append(
            f"- [{e.get('entity_type')}] {e.get('name')} (ID: {e.get('id')}){pos}: {description}..."
        )
    return "\n".join(lines)


async def plot_context(ctx: DebugContext) -> str:
    res = await ctx.db.execute(
        select(AdventureTemplate).where(AdventureTemplate.id == ctx.state.adventure_id)
    )
    adv = res.scalars().first()
    return f"--- DEBUG: PLOT CONTEXT ---\n{adv.original_prompt}"


async def world_stats(ctx: DebugContext) -> str:
    session_id = ctx.state.session_id
    scenes = await ctx.db.execute(select(WorldScene).where(WorldScene.session_id == session_id))
    entities = await ctx.db.execute(select(WorldEntity).where(WorldEntity.session_id == session_id))
    exits = await ctx.db.execute(select(WorldExit).where(WorldExit.session_id == session_id))
    return (
        f"--- DEBUG: WORLD STATS ---\n"
        f"AdventureTemplate ID: {ctx.state.adventure_id}\n"
        f"Session ID: {session_id}\n"
        f"Total Scenes: {len(scenes.scalars().all())}\n"
        f"Total Entities: {len(entities.scalars().all())}\n"
        f"Total Connections: {len(exits.scalars().all())}"
    )


async def session_info(ctx: DebugContext) -> str:
    scene = await _current_scene(ctx)
    label = scene.label if scene else "Unknown"
    state = ctx.state
    return (
        f"--- DEBUG: SESSION STATE ---\n"
        f"Session ID: {state.session_id}\n"
        f"Current Scene: {label} (ID: {state.scene_id})\n"
        f"In-Game Time: {state.in_game_time} minutes\n"
        f"Debug Logging: {'ON' if state.is_debug_enabled else 'OFF'}"
    )


async def engine_info(ctx: DebugContext) -> str:
    lines = [
        "--- DEBUG: ENGINE DIAGNOSTICS ---",
        f"TaleWeaver Version: {settings.APP_VERSION}",
        f"Platform: {platform.platform()}",
        f"Python Version: {sys.version.split(' ')[0]}",
        f"Server Time: {datetime.now().isoformat()}",
        f"Current Session ID: {ctx.state.session_id}",
        f"Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}",
        f"Data Dir: {settings.DATA_DIR}",
    ]
    return "\n".join(lines)


async def list_scenes(ctx: DebugContext) -> str:
    scenes = await session_scene_labels(ctx)
    if not scenes:
        return "DEBUG: No scenes found for this session."
    lines = ["--- DEBUG: ALL SCENES ---"]
    lines.extend(f"- {label} (ID: {scene_id})" for scene_id, label in scenes.items())
    return "\n".join(lines)


async def list_npcs(ctx: DebugContext) -> str:
    npcs_db = await session_entities(ctx, "NPC")
    if not npcs_db:
        return "--- DEBUG: No NPCs found for this session. ---"
    overrides = ctx.state.entity_states or {}
    scene_map = await session_scene_labels(ctx)
    lines = ["--- DEBUG: ALL NPCs ---"]
    for npc in (entity_with_overrides(e, overrides) for e in npcs_db):
        curr_scene = npc.get("current_scene_id")
        loc_label = scene_map.get(curr_scene, curr_scene)
        pos = position_suffix(npc, " ({})")
        lines.append(f"- {npc.get('name')} (ID: {npc.get('id')}) @ {loc_label}{pos}")
    return "\n".join(lines)


def _item_location(item: dict, scene_map: dict[str, str]) -> str:
    if item.get("is_in_inventory"):
        return "Inventory"
    curr_scene = item.get("current_scene_id")
    loc_label = scene_map.get(curr_scene, curr_scene)
    return f"Scene: {loc_label}{position_suffix(item, ' ({})')}"


async def list_items(ctx: DebugContext) -> str:
    items_db = await session_entities(ctx, "OBJECT")
    if not items_db:
        return "--- DEBUG: No items found for this session. ---"
    overrides = ctx.state.entity_states or {}
    scene_map = await session_scene_labels(ctx)
    lines = ["--- DEBUG: ALL ITEMS ---"]
    for item in (entity_with_overrides(e, overrides) for e in items_db):
        lines.append(
            f"- {item.get('name')} (ID: {item.get('id')}) @ {_item_location(item, scene_map)}"
        )
    return "\n".join(lines)


async def list_exits(ctx: DebugContext) -> str:
    res = await ctx.db.execute(
        select(WorldExit).where(WorldExit.session_id == ctx.state.session_id)
    )
    exits = res.scalars().all()
    if not exits:
        return "DEBUG: No exits found for this session."
    lines = ["--- DEBUG: ALL EXITS ---"]
    for e in exits:
        locked = "[LOCKED]" if e.is_locked else "[OPEN]"
        exit_id = e.id if hasattr(e, "id") else "N/A"
        lines.append(f"- {e.label} (ID: {exit_id}): {e.from_scene_id} -> {e.to_scene_id} {locked}")
    return "\n".join(lines)
