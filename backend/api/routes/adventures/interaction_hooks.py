"""Runs the ``on_interact`` triggers of one entity the player interacted with this message.

Two sources fire, in this order:

1. Top-level and active-sequence scripts with ``trigger == "on_interact"`` targeting the entity.
2. The entity's own inline trigger (``on_interact_script`` / ``on_interact_text`` in the
   ``metadata_json`` of an object or NPC).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.engine.scripting import ScriptMessage
from backend.models.world_entity import WorldEntity

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from backend.engine.scripting import ScriptRunner


async def _entity_metadata(manager: GameTurnManager, entity_id: str) -> dict[str, Any]:
    res = await manager.db.execute(
        select(WorldEntity.metadata_json).where(
            WorldEntity.session_id == manager.state.session_id, WorldEntity.id == entity_id
        )
    )
    metadata = res.scalars().first()
    return metadata if isinstance(metadata, dict) else {}


async def _run_scripts(
    manager: GameTurnManager, runner: ScriptRunner, entity_id: str, game_event: Any
) -> tuple[list[Any], list[str]]:
    if not runner.scripts:
        return [], []
    context = await manager._build_script_context()
    changeset = runner.run_trigger("on_interact", context, target_id=entity_id)
    messages = await manager._apply_script_changeset(changeset, game_event)
    return list(messages), list(changeset.rejected_actions)


async def _run_inline(manager: GameTurnManager, entity_id: str) -> list[Any]:
    metadata = await _entity_metadata(manager, entity_id)
    code = str(metadata.get("on_interact_script") or "").strip()
    text = str(metadata.get("on_interact_text") or "").strip()
    messages: list[Any] = []
    if code:
        messages.extend(await manager._execute_inline_script(code, "on_interact", entity_id))
    if text:
        await manager._save_chat_message("system", text)
        messages.append(ScriptMessage(text, role="system"))
    return messages


async def fire_interact_triggers(
    manager: GameTurnManager, runner: ScriptRunner, entity_id: str, game_event: Any
) -> tuple[list[Any], list[str]]:
    """Returns (messages to show, rejected actions) for one interacted entity."""
    messages, rejected = await _run_scripts(manager, runner, entity_id, game_event)
    messages.extend(await _run_inline(manager, entity_id))
    return messages, rejected
