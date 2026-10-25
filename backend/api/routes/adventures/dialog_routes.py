"""Endpoint for answering script-opened choice dialogs (``tw.dialog.choose``)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.scripting.dialog import pending_dialog
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])

PENDING_DIALOG_DETAIL = "Answer the open choice before continuing."


class DialogChoiceRequest(BaseModel):
    dialog_id: str = Field(..., min_length=1, max_length=64)
    index: int = Field(..., ge=0)
    language: Optional[str] = None


async def ensure_no_pending_dialog(db: AsyncSession, game_id: str, user: User) -> None:
    """Rejects free-text turns while a choice dialog awaits the player's answer."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=user.id)
    if state and pending_dialog(state.entity_states) is not None:
        raise HTTPException(status_code=409, detail=PENDING_DIALOG_DETAIL)


@router.post("/{game_id}/dialog/choice")
async def answer_dialog_choice(
    game_id: str,
    payload: DialogChoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Applies the player's choice and runs the dialog's on_choice handler."""
    resolver = await DialogChoiceResolver.create(db, game_id, current_user)
    return await resolver.resolve(payload.dialog_id, payload.index, payload.language)
