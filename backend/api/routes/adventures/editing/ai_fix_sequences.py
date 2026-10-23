"""Sequence support for AI fix suggestions: prompt context and patch application.

Sequences are not world entities; they live as a JSON list on the adventure
template (``AdventureTemplate.sequences``) and are mirrored into the original
manifest, exactly like the editor's sequence save path.
"""

import json
from typing import Any, Optional

from fastapi import HTTPException

from backend.api.routes.adventures.templates import _apply_sequences_update
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.models.adventure_template import AdventureTemplate

_GUARD_FIELDS = ("guard_expression", "completion_guard_expression")
_REQUIREMENT_FIELDS = ("required_item_id", "required_scene_id", "required_defeated_npc_id")
_OUTLINE_TEXT_LIMIT = 200
_DETAIL_TEXT_LIMIT = 1500


def _short(value: Any, limit: int) -> str:
    text = "" if value is None else str(value).strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _upper_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _sorted_sequences(sequences: Any) -> list[dict[str, Any]]:
    rows = [s for s in (sequences or []) if isinstance(s, dict)]
    return sorted(rows, key=lambda s: s.get("order") if isinstance(s.get("order"), int) else 0)


def sequence_outline(seq: dict[str, Any]) -> dict[str, Any]:
    """Compact sequence row: enough to reason about chapter order and gating."""
    return {
        "id": seq.get("id"),
        "order": seq.get("order"),
        "title": seq.get("title"),
        "end_condition": _short(seq.get("end_condition"), _OUTLINE_TEXT_LIMIT),
        "guard_expression": seq.get("guard_expression") or "",
        "completion_guard_expression": seq.get("completion_guard_expression") or "",
    }


def sequence_detail(seq: dict[str, Any]) -> dict[str, Any]:
    """Full sequence row for the finding's target (walkthrough included)."""
    detail = sequence_outline(seq)
    detail.update(
        description=_short(seq.get("description"), _DETAIL_TEXT_LIMIT),
        walkthrough=_short(seq.get("walkthrough"), _DETAIL_TEXT_LIMIT),
        end_condition=_short(seq.get("end_condition"), _DETAIL_TEXT_LIMIT),
        on_start_sequence_text=_short(seq.get("on_start_sequence_text"), _OUTLINE_TEXT_LIMIT),
        on_end_sequence_text=_short(seq.get("on_end_sequence_text"), _OUTLINE_TEXT_LIMIT),
        on_start_sequence_script=_short(seq.get("on_start_sequence_script"), _OUTLINE_TEXT_LIMIT),
        on_end_sequence_script=_short(seq.get("on_end_sequence_script"), _OUTLINE_TEXT_LIMIT),
    )
    detail.update({field: seq.get(field) or "" for field in _REQUIREMENT_FIELDS})
    return detail


def summarize_sequences(sequences: Any) -> list[dict[str, Any]]:
    """Full sequence rows in chapter order, as stored in the world summary."""
    return [sequence_detail(s) for s in _sorted_sequences(sequences)]


def format_sequence_outline(summary: dict[str, Any]) -> str:
    outline = [sequence_outline(s) for s in summary.get("sequences") or []]
    return json.dumps(outline, ensure_ascii=False) if outline else "(none)"


def focus_sequence(summary: dict[str, Any], target_id: str) -> tuple[str, list[tuple[str, Any]]]:
    """Target block for a sequence finding plus the previous and next chapters."""
    sequences = summary.get("sequences") or []
    wanted = _upper_id(target_id)
    idx = next((i for i, s in enumerate(sequences) if _upper_id(s.get("id")) == wanted), None)
    if idx is None:
        return "", []
    target = sequences[idx]
    block = (
        f"=== TARGET SEQUENCE ({target.get('id')}) ===\n{json.dumps(target, ensure_ascii=False)}\n"
    )
    neighbors = [("sequence", sequences[j]) for j in (idx - 1, idx + 1) if 0 <= j < len(sequences)]
    return block, neighbors


def _find_sequence_index(sequences: list[Any], raw_target_id: str) -> Optional[int]:
    """Match by exact id (case-insensitive), else by a unique title."""
    wanted = _upper_id(raw_target_id)
    rows = [(i, s) for i, s in enumerate(sequences) if isinstance(s, dict)]
    by_id = next((i for i, s in rows if _upper_id(s.get("id")) == wanted), None)
    if by_id is not None:
        return by_id
    title = raw_target_id.strip().lower()
    by_title = [i for i, s in rows if str(s.get("title") or "").strip().lower() == title]
    return by_title[0] if len(by_title) == 1 else None


def _validated_value(field: str, value: Any) -> str:
    text = str(value).strip()
    if field not in _GUARD_FIELDS or not text:
        return text
    errors = SafeAstInterpreter.check_expression_syntax(text)
    if errors:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {errors[0]}")
    return text


def patch_sequence(adv: AdventureTemplate, raw_target_id: str, updates: dict[str, Any]) -> str:
    """Apply allowlisted field updates to one sequence of the template."""
    sequences = list(adv.sequences or [])
    idx = _find_sequence_index(sequences, raw_target_id)
    if idx is None:
        # ``ai_fix_apply`` treats "could not be resolved" as a stale cached proposal.
        raise HTTPException(
            status_code=400,
            detail=(
                f"sequence '{raw_target_id}' could not be resolved in this adventure. "
                "The AI reference is stale; please retry."
            ),
        )
    updated = dict(sequences[idx])
    updated.update({field: _validated_value(field, value) for field, value in updates.items()})
    sequences[idx] = updated
    _apply_sequences_update(adv, sequences)
    return f"sequence:{updated.get('id')}"
