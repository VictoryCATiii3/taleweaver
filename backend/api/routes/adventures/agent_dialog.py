"""Play-agent answers to script-opened choice dialogs (``tw.dialog.choose``).

While a dialog is open the agent must not play a free-text turn: it picks one of the offered
options instead. Monkey mode picks at random; otherwise the agent's model chooses, guided by
the current walkthrough, and falls back to the first option when no usable answer comes back.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.routes.adventures.agent_logic import (
    AgentService,
    _build_agent_objective_and_walkthrough,
    format_agent_history,
)
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import get_play_agent_personality_prompt
from backend.models.chat import ChatMessage

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 8
_SYSTEM_PROMPT = (
    "You are an autonomous player of a text adventure. The game shows you a choice dialog and "
    "you must pick exactly one of the numbered options.\n\n"
    "{personality_prompt}\n\n{objective_block}\n\n{walkthrough_text}"
)


class AgentDialogDecision(BaseModel):
    thoughts: str = Field(description="Short in-character reasoning for the choice.")
    option_number: int = Field(description="1-based number of the chosen option.")


def _options_text(dialog: dict[str, Any]) -> str:
    return "\n".join(f"{n}. {o['label']}" for n, o in enumerate(dialog["options"], start=1))


async def _recent_history(manager: Any) -> str:
    res = await manager.db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == manager.state.session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = reversed(list(res.scalars().all()))
    return format_agent_history([{"role": r.role, "content": r.content} for r in rows])


async def _ask_model(
    manager: Any, dialog: dict[str, Any], agent_state: dict[str, Any]
) -> AgentDialogDecision | None:
    objective_block, walkthrough_text = _build_agent_objective_and_walkthrough(
        manager.adventure, manager.state, agent_state
    )
    llm_settings = manager.user.llm_settings or {}
    personality_prompt = get_play_agent_personality_prompt(
        agent_state.get("personality") or llm_settings.get("play_agent_personality") or "casual",
        agent_state.get("custom_personality") or "",
    )
    system_prompt = _SYSTEM_PROMPT.format(
        personality_prompt=personality_prompt,
        objective_block=objective_block,
        walkthrough_text=walkthrough_text,
    )
    speaker = f"{dialog['speaker']} asks: " if dialog.get("speaker") else ""
    user_prompt = (
        f"RECENT GAME HISTORY (oldest first):\n{await _recent_history(manager)}\n\n"
        f"CHOICE DIALOG:\n{speaker}{dialog.get('prompt') or ''}\n\n"
        f"OPTIONS:\n{_options_text(dialog)}\n\n"
        "Which option number do you choose?"
    )
    provider = (
        llm_settings.get("play_agent_model_provider")
        or llm_settings.get("small_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = llm_settings.get("play_agent_model") or llm_settings.get("small_model") or "gpt-4o-mini"
    try:
        llm = GameMasterLLM(user=manager.user, provider=provider, model_category="small")
        return await llm.aexecute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=AgentDialogDecision,
            model=model,
            adventure_id=manager.adventure.id,
            game_id=manager.game_id,
            operation="agent_dialog_choice",
            phase="decision",
        )
    except Exception:
        logger.exception("[Agent] Dialog choice decision failed for %s", manager.game_id)
        return None


async def decide_dialog_option(manager: Any, dialog: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Returns (thoughts, chosen option) for the open dialog."""
    options = dialog["options"]
    agent_state = AgentService.get_agent_state(manager.state)
    if agent_state.get("monkey_mode"):
        return "Monkey mode: picking a random answer.", secrets.choice(options)
    decision = await _ask_model(manager, dialog, agent_state)
    if decision is None or not 1 <= decision.option_number <= len(options):
        return "No usable decision; taking the first answer.", options[0]
    return decision.thoughts, options[decision.option_number - 1]
