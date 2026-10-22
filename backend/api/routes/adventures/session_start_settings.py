"""Resolves where (initial scene) and when (in-game start datetime) a new session begins."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldExit, WorldScene

logger = logging.getLogger(__name__)

_RELATIVE_TIME_SYSTEMS = ("relative", "units")
_DEFAULT_START_TIME = "08:00"
_DEFAULT_START_HOUR_MINUTE = (8, 0)
_DEFAULT_START_YEAR = 2026
_FALLBACK_SCENE_ID = "START"
_EXPLICIT_START_KEYS = ("start_scene_id", "scene_id", "current_scene_id")


def _parse_iso(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _merged_time_config(manifest: dict[str, Any], time_config: Optional[dict]) -> dict[str, Any]:
    """Editor time_config wins over manifest defaults so the world editor can set the start."""
    merged = dict(time_config or {})
    manifest_time_config = manifest.get("time_config")
    if isinstance(manifest_time_config, dict):
        for key, value in manifest_time_config.items():
            merged.setdefault(key, value)
    return merged


def _from_date_and_time(config: dict[str, Any], manifest: dict[str, Any]) -> Optional[str]:
    start_date = config.get("start_date") or manifest.get("start_date")
    if not isinstance(start_date, str) or not start_date.strip():
        return None
    start_time = config.get("start_time") or manifest.get("start_time")
    has_time = isinstance(start_time, str) and start_time.strip()
    time_part = start_time.strip() if has_time else _DEFAULT_START_TIME
    return _parse_iso(f"{start_date.strip()}T{time_part}")


def _hour_minute(configured_start: Any) -> tuple[int, int]:
    if not isinstance(configured_start, str) or not configured_start.strip():
        return _DEFAULT_START_HOUR_MINUTE
    try:
        hour, minute = map(int, configured_start.strip().split(":"))
    except ValueError:
        logger.debug("Ignoring malformed start_time %r", configured_start)
        return _DEFAULT_START_HOUR_MINUTE
    return hour, minute


def _from_time_and_year(config: dict[str, Any]) -> Optional[str]:
    """Builds Jan 1st of the (overridden) year at ``start_time`` (e.g. "14:30")."""
    configured_start = config.get("start_time")
    year_override = config.get("start_year_override")
    if not configured_start and not year_override:
        return None
    hour, minute = _hour_minute(configured_start)
    try:
        year = int(year_override) if year_override else _DEFAULT_START_YEAR
        return datetime(year=year, month=1, day=1, hour=hour, minute=minute).isoformat()
    except (TypeError, ValueError):
        return None


def resolve_start_datetime(
    manifest: Optional[dict[str, Any]],
    state: Optional[SessionState] = None,
    time_config: Optional[dict] = None,
) -> Optional[str]:
    """Returns a usable ISO datetime string. Prioritizes session-specific state over manifest."""
    if state and state.start_datetime:
        return state.start_datetime

    target_manifest = manifest or {}
    config = _merged_time_config(target_manifest, time_config)
    time_system = config.get("time_system") or target_manifest.get("time_system")
    if time_system in _RELATIVE_TIME_SYSTEMS:
        return None
    return (
        _parse_iso(config.get("start_datetime"))
        or _parse_iso(target_manifest.get("start_datetime"))
        or _from_date_and_time(config, target_manifest)
        or _from_time_and_year(config)
    )


def _manifest_start_scene(manifest: Any, scene_set: set[str]) -> Optional[str]:
    """Explicit start scene from the manifest, else the first manifest scene that exists."""
    if not isinstance(manifest, dict):
        return None
    explicit = next((manifest.get(key) for key in _EXPLICIT_START_KEYS if manifest.get(key)), None)
    if isinstance(explicit, str) and explicit.strip() in scene_set:
        return explicit.strip()
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list):
        return None
    ids = (entry.get("id") for entry in scenes if isinstance(entry, dict))
    return next(
        (sid.strip() for sid in ids if isinstance(sid, str) and sid.strip() in scene_set), None
    )


async def _entry_scene(db: AsyncSession, template_id: str, scene_set: set[str]) -> str:
    """First scene (sorted) without incoming exits, else the first scene id overall."""
    exit_res = await db.execute(
        select(WorldExit.from_scene_id, WorldExit.to_scene_id).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    reachable = {
        to_scene_id
        for from_scene_id, to_scene_id in exit_res.all()
        if from_scene_id in scene_set and to_scene_id in scene_set
    }
    entry_scenes = sorted(scene_set - reachable)
    return entry_scenes[0] if entry_scenes else sorted(scene_set)[0]


async def resolve_initial_scene_id(db: AsyncSession, template_id: Optional[str]) -> str:
    """Resolve a stable initial scene for a fresh session.

    Priority:
    1) Explicit scene from template manifest (`start_scene_id`, `scene_id`, `current_scene_id`).
    2) First scene in template manifest order.
    3) Scene with id "START" when present.
    4) Entry scene(s) with no incoming exits (template baseline only).
    5) Lexicographically first available scene id.
    6) Fallback "START" when no scenes exist.
    """
    if not template_id:
        return _FALLBACK_SCENE_ID

    scene_res = await db.execute(
        select(WorldScene.id).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scene_set = {sid for sid in scene_res.scalars().all() if isinstance(sid, str) and sid}
    if not scene_set:
        return _FALLBACK_SCENE_ID

    adv_res = await db.execute(
        select(AdventureTemplate.original_manifest).where(AdventureTemplate.id == template_id)
    )
    from_manifest = _manifest_start_scene(adv_res.scalar_one_or_none(), scene_set)
    if from_manifest:
        return from_manifest
    if _FALLBACK_SCENE_ID in scene_set:
        return _FALLBACK_SCENE_ID
    return await _entry_scene(db, template_id, scene_set)
