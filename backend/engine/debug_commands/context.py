"""Shared context and helpers for ``/debug`` sub-command handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene


@dataclass
class DebugContext:
    db: AsyncSession
    state: SessionState
    args: str
    user: Optional[User] = None
    adventure: Optional[AdventureTemplate] = None
    avatar: Optional[Any] = None

    @property
    def parts(self) -> list[str]:
        return self.args.split(" ")


DebugHandler = Callable[[DebugContext], Awaitable[Optional[str]]]


async def session_entities(ctx: DebugContext, entity_type: Optional[str] = None) -> list[Any]:
    query = select(WorldEntity).where(WorldEntity.session_id == ctx.state.session_id)
    if entity_type:
        query = query.where(WorldEntity.entity_type == entity_type)
    res = await ctx.db.execute(query)
    return list(res.scalars().all())


async def session_scene_labels(ctx: DebugContext) -> dict[str, str]:
    res = await ctx.db.execute(
        select(WorldScene).where(WorldScene.session_id == ctx.state.session_id)
    )
    return {s.id: s.label for s in res.scalars().all()}


def entity_with_overrides(entity: Any, overrides: dict[str, Any]) -> dict[str, Any]:
    """Column values of an entity merged with its session-state overrides."""
    data = {c.name: getattr(entity, c.name) for c in entity.__table__.columns}
    data.update(overrides.get(entity.id) or {})
    return data


def set_entity_state(ctx: DebugContext, entity_id: str, key: str, value: Any) -> None:
    states = dict(ctx.state.entity_states or {})
    entry = dict(states.get(entity_id) or {})
    entry[key] = value
    states[entity_id] = entry
    ctx.state.entity_states = states
    flag_modified(ctx.state, "entity_states")


def position_suffix(data: dict[str, Any], template: str) -> str:
    position = data.get("spatial_position")
    return template.format(position) if position else ""
