"""Sequence (chapter) transition hooks: end/start scripts and texts, and the chapter intro prompt."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

SaveChatMessage = Callable[[str, str], Awaitable[Any]]


def _find_sequence(adventure: Any, seq_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not seq_id:
        return None
    for seq in getattr(adventure, "sequences", None) or []:
        if isinstance(seq, dict) and seq.get("id") == seq_id:
            return seq
    return None


async def _run_hook(
    manager: Any,
    save_chat_message: SaveChatMessage,
    seq: dict[str, Any],
    hook: str,
) -> list[Any]:
    messages: list[Any] = []
    script = seq.get(f"{hook}_script")
    if script:
        messages.extend(await manager._execute_inline_script(script, hook, seq.get("id")))
    text = seq.get(f"{hook}_text")
    if text:
        await save_chat_message("system", text)
        messages.append(text)
    return messages


async def run_sequence_transition_hooks(
    manager: Any,
    save_chat_message: SaveChatMessage,
    adventure: Any,
    old_seq_id: Optional[str],
    new_seq_id: Optional[str],
) -> list[Any]:
    """Runs on_end_sequence of the completed and on_start_sequence of the new sequence.

    Returns the produced system messages (script output and texts) in order.
    """
    messages: list[Any] = []
    completed = _find_sequence(adventure, old_seq_id)
    if completed:
        messages.extend(await _run_hook(manager, save_chat_message, completed, "on_end_sequence"))
    started = _find_sequence(adventure, new_seq_id)
    if started and started is not completed:
        messages.extend(await _run_hook(manager, save_chat_message, started, "on_start_sequence"))
    return messages


def build_sequence_intro(adventure: Any, seq_id: Optional[str]) -> Optional[dict[str, Any]]:
    """Pending narration that opens a newly started sequence, or None if there is none."""
    seq = _find_sequence(adventure, seq_id)
    if not seq:
        return None
    title = seq.get("title") or seq.get("id")
    description = str(seq.get("description") or "").strip()
    prompt = (
        f"[SEQUENCE_START] A new chapter begins: {title}. "
        "Narrate a short opening for this chapter in one or two paragraphs, set in the current "
        "scene: what the player now faces and what draws their attention next. "
        "Do NOT change world state, award items, move the player, or resolve the chapter goal."
    )
    if description:
        prompt += f" Chapter premise (do not quote verbatim): {description}"
    return {"prompt": prompt, "title": title}
