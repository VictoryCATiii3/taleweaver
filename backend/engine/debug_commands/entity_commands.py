"""``/debug`` sub-commands that change entities or the player's avatar."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.debug_commands.context import (
    DebugContext,
    session_entities,
    set_entity_state,
)


def _parse_heal_args(parts: list[str]) -> tuple[str, Optional[int]]:
    """``heal <name...> [amount]`` -> (lowercased name, amount or None)."""
    try:
        return " ".join(parts[1:-1]).lower(), int(parts[-1])
    except ValueError:
        return " ".join(parts[1:]).lower(), None


async def heal(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug heal [NPC_NAME] [AMOUNT?]"
    npc_name, amount = _parse_heal_args(parts)
    entities = await session_entities(ctx)
    target = next(
        (e for e in entities if e.name.lower() == npc_name or e.id.lower() == npc_name), None
    )
    if not target:
        return f"DEBUG: NPC/Entity '{npc_name}' not found in this session."
    final_hp = amount if amount is not None else (target.hp or 50)
    set_entity_state(ctx, target.id, "hp", final_hp)
    return f"DEBUG: Entity '{target.name}' (ID: {target.id}) restored to {final_hp} HP."


def _matches_name_or_id(entity: Any, target: str) -> bool:
    return entity.id == target or (
        isinstance(entity.name, str) and entity.name.lower() == target.lower()
    )


async def _unhide_all(ctx: DebugContext) -> str:
    entities = await session_entities(ctx)
    if not entities:
        return "DEBUG: No entities found in this session."
    for entity in entities:
        set_entity_state(ctx, entity.id, "is_hidden", False)
    await ctx.db.commit()
    return f"DEBUG: Unhid {len(entities)} entities in this session."


async def unhide(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug unhide [ENTITY_ID|NAME|all]"
    target = " ".join(parts[1:]).strip()
    if target.lower() == "all":
        return await _unhide_all(ctx)

    entities = await session_entities(ctx)
    found = next((e for e in entities if _matches_name_or_id(e, target)), None)
    if not found:
        return f"DEBUG: Entity '{target}' not found in this session."
    set_entity_state(ctx, found.id, "is_hidden", False)
    await ctx.db.commit()
    return f"DEBUG: Entity '{found.name}' (ID: {found.id}) is now visible."


async def _find_npc(ctx: DebugContext, target: str) -> Optional[Any]:
    npcs = await session_entities(ctx, "NPC")
    return next(
        (
            e
            for e in npcs
            if e.id.upper() == target.upper() or (e.name and e.name.lower() == target.lower())
        ),
        None,
    )


async def npc_note(ctx: DebugContext) -> str:
    parts = ctx.args.split(" ", 2)
    if len(parts) < 3:
        return "DEBUG ERROR: Usage: /debug npc_note [NPC_ID|NAME] [note text]"
    target, note_val = parts[1].strip(), parts[2].strip()
    found = await _find_npc(ctx, target)
    if not found:
        return f"DEBUG ERROR: NPC '{target}' not found in session."
    set_entity_state(ctx, found.id, "notes", note_val)
    await ctx.db.commit()
    return f"DEBUG: NPC '{found.name}' notes set to: \"{note_val}\""


async def moveable(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 3:
        return "DEBUG ERROR: Usage: /debug moveable [NPC_ID|NAME] [true|false]"
    target = parts[1].strip()
    value = parts[2].strip().lower() in ("true", "1", "yes")
    found = await _find_npc(ctx, target)
    if not found:
        return f"DEBUG ERROR: NPC '{target}' not found in session."
    set_entity_state(ctx, found.id, "moveable", value)
    await ctx.db.commit()
    return f"DEBUG: NPC '{found.name}' moveable set to {value}."


async def delete_item(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug delete_item [ITEM_KEY]"
    item_key = parts[1]
    avatar = ctx.avatar
    if not avatar:
        return "DEBUG ERROR: Avatar context missing."
    inventory = list(avatar.inventory or [])
    remaining = [
        item for item in inventory if item.get("id") != item_key and item.get("key") != item_key
    ]
    if len(remaining) == len(inventory):
        return f"DEBUG: Item '{item_key}' not found in inventory."
    avatar.inventory = remaining
    flag_modified(avatar, "inventory")
    return f"DEBUG: Item '{item_key}' removed from inventory."


async def grant_exp(ctx: DebugContext) -> str:
    parts = ctx.parts
    if len(parts) < 2:
        return "DEBUG ERROR: Usage: /debug exp [AMOUNT]"
    try:
        amount = int(parts[1])
    except ValueError:
        return "DEBUG ERROR: Amount must be an integer."
    avatar = ctx.avatar
    if not avatar:
        return "DEBUG ERROR: Avatar context missing."
    avatar.exp = (avatar.exp or 0) + amount
    return f"DEBUG: Granted {amount} XP to {avatar.name}. New total: {avatar.exp}"
