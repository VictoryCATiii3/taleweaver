"""Endpoint that asks the LLM for fix proposals for a validation finding."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_context import (
    _format_finding_context_block,
    _format_focused_world_block,
    _signing,
    _summarize_world_for_fix,
)
from backend.api.routes.adventures.editing.ai_fix_limits import format_length_limits
from backend.api.routes.adventures.editing.ai_fix_llm import (
    _AllProvidersFailedError,
    _generate_llm_proposals,
    _get_cached_suggestions,
    _summarize_outcomes,
    _write_cached_suggestions,
)
from backend.api.routes.adventures.editing.ai_fix_sanitize import sanitize_proposals
from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.schemas import AISuggestFixWrapperResponse
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.validators_prompts import AI_FIX_SUGGESTIONS_SYSTEM_PROMPT
from backend.models.user import User
from backend.schemas.validation import (
    AIFixSuggestionsRequest,
    AIFixSuggestionsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_MAX_PROPOSALS = 3
_TIMEOUT_MESSAGE = "The AI service did not respond in time. Please retry in a moment."
_UNAVAILABLE_MESSAGE = "The AI service is currently unavailable. Please retry in a moment."
_SYSTEM_PROMPT = AI_FIX_SUGGESTIONS_SYSTEM_PROMPT + format_length_limits()


def _suggestion_prompt(payload: AIFixSuggestionsRequest, summary: dict[str, Any]) -> str:
    world_block = _format_focused_world_block(summary, location=payload.finding_location)
    return (
        f"=== ORIGINAL FINDING ===\n"
        f"- Code: {payload.finding_code}\n"
        f"- Severity: {payload.finding_severity}\n"
        f"- Location: {(payload.finding_location or '').strip()}\n"
        f"- Message: {payload.finding_message}\n"
        f"{_format_finding_context_block(payload)}\n\n"
        f"{world_block}\n"
        f"Produce up to 3 distinct, immediately applicable fix proposals for the finding above.\n"
        f"Return ONLY the JSON object with a top-level 'proposals' key."
    )


def _failure_message(exc: Exception, template_id: str) -> str:
    """User-facing, provider-neutral message for a failed suggestion call (logged here)."""
    if isinstance(exc, _AllProvidersFailedError):
        logger.warning("AI fix suggestion unavailable for %s: %s", template_id, exc)
        return _summarize_outcomes(exc.outcomes)
    if isinstance(exc, TimeoutError):
        logger.warning(
            "AI fix suggestion timed out for %s after %.0fs: %s",
            template_id,
            settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            exc,
        )
        return _TIMEOUT_MESSAGE
    logger.exception("AI fix suggestion failed for %s: %s", template_id, exc)
    return _UNAVAILABLE_MESSAGE


async def _valid_cached_response(
    db: AsyncSession, template_id: str, user_id: str, signature: str, summary: dict[str, Any]
) -> Optional[AIFixSuggestionsResponse]:
    """Cached proposals re-checked against the current limits (None to regenerate)."""
    cached = await _get_cached_suggestions(
        db=db, template_id=template_id, user_id=user_id, signature=signature
    )
    if not cached:
        return None
    response = AIFixSuggestionsResponse(**{**cached, "error": None})
    raw = [p.model_dump() for p in response.proposals]
    response.proposals = sanitize_proposals(raw, summary).proposals
    return response if response.proposals else None


async def _cache_response(
    db: AsyncSession, template_id: str, user_id: str, response: AIFixSuggestionsResponse
) -> None:
    try:
        await _write_cached_suggestions(
            db=db,
            template_id=template_id,
            user_id=user_id,
            signature=response.finding_signature,
            response_payload=response.model_dump(),
        )
    except Exception as cache_exc:
        logger.warning(
            "Failed to persist AI fix cache for %s/%s: %s",
            template_id,
            response.finding_signature,
            cache_exc,
        )


@router.post(
    "/{template_id}/editor/validate/findings/suggest-fix",
    response_model=AIFixSuggestionsResponse,
)
async def ai_suggest_fix_for_finding(
    template_id: str,
    payload: AIFixSuggestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest up to 3 different fixes for an AI-detected validation finding.

    Fast-path on cache hit (per (template, user, finding_signature)).
    Otherwise: focused world context, hard watchdog, provider fallback,
    persist on success. Always returns HTTP 200 with either proposals or a
    short, anbieter-neutral ``error`` string.
    """
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return await generate_fix_proposals(db, template_id, current_user, payload)


async def generate_fix_proposals(
    db: AsyncSession,
    template_id: str,
    current_user: User,
    payload: AIFixSuggestionsRequest,
) -> AIFixSuggestionsResponse:
    """Cached-or-generated fix proposals for one finding (ownership is checked by callers)."""
    # Read before the cache lookup, which may commit/rollback and expire ``current_user``.
    user_id = current_user.id
    signature = _signing(payload)
    summary = _summarize_world_for_fix(await _build_adventure_editor_assets(template_id, db))
    cached = await _valid_cached_response(db, template_id, user_id, signature, summary)
    if cached:
        return cached

    user_prompt = _suggestion_prompt(payload, summary)
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapper, _served_provider = await _generate_llm_proposals(
            user_prompt=user_prompt,
            current_user=current_user,
            response_model=AISuggestFixWrapperResponse,
            gm_kwargs={"system_prompt": _SYSTEM_PROMPT},
            timeout_seconds=settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
            allow_fallback=True,
        )
    except Exception as exc:
        return AIFixSuggestionsResponse(
            finding_signature=signature,
            proposals=[],
            generated_at=generated_at,
            error=_failure_message(exc, template_id),
        )

    raw_proposals = ((wrapper.proposals if wrapper else []) or [])[:_MAX_PROPOSALS]
    sanitized = sanitize_proposals(raw_proposals, summary)
    response = AIFixSuggestionsResponse(
        finding_signature=signature,
        proposals=sanitized.proposals,
        generated_at=generated_at,
    )
    if not raw_proposals:
        logger.info("AI declined to suggest fixes for %s (%s)", template_id, payload.finding_code)
    if sanitized.rejected:
        logger.warning(
            "AI fix proposals for %s (%s): kept %d of %d, rejected: %s",
            template_id,
            payload.finding_code,
            len(sanitized.proposals),
            len(raw_proposals),
            "; ".join(sanitized.rejected),
        )
    if raw_proposals and not sanitized.proposals:
        response.error = sanitized.error_message()
    if response.proposals:
        await _cache_response(db, template_id, user_id, response)
    return response
