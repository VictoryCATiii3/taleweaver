"""Sanitizes raw LLM fix proposals into applicable ``FixProposal`` objects.

Drops patches for unsupported targets/fields and whole proposals whose values
exceed the editor's field length limits, recording why so the user is told
instead of seeing an unexplained empty result.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, get_args

from backend.api.routes.adventures.editing.ai_fix_limits import length_violations
from backend.api.routes.adventures.editing.ai_fix_targets import _allowed_fields_for
from backend.schemas.validation import FixProposal, FixProposalEntityPatch, FixTargetType

_PATCH_TARGET_TYPES = frozenset(get_args(FixTargetType))
_MAX_REJECTED_LISTED = 5
_PROPOSAL_FIELDS = (
    "title",
    "summary",
    "rationale",
    "patches",
    "target_type",
    "target_id",
    "description",
    "field_updates",
    "note",
)
_DROPPED_MESSAGE = (
    "The AI proposed changes the editor cannot apply automatically ({rejected}). "
    "Try fixing it manually or request new suggestions."
)
_DROPPED_FALLBACK = "incomplete proposals without applicable patches"


def _as_dict(value: Any) -> Optional[dict[str, Any]]:
    """Normalize an LLM-returned proposal/patch (dict, pydantic model, or object) to a dict."""
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            return None
        return dumped if isinstance(dumped, dict) else None
    collected = {f: getattr(value, f) for f in _PROPOSAL_FIELDS if hasattr(value, f)}
    return collected or None


def _object_item_types(summary: dict[str, Any]) -> dict[str, str]:
    """Object ``item_type`` keyed by upper-cased id and name (the AI may use either)."""
    item_types: dict[str, str] = {}
    for obj in summary.get("objects") or []:
        item_type = str(obj.get("item_type") or "").upper()
        for key in (obj.get("id"), obj.get("name")):
            item_types[str(key or "").strip().upper()] = item_type
    return item_types


@dataclass
class SanitizedProposals:
    proposals: list[FixProposal]
    rejected: list[str] = field(default_factory=list)

    def error_message(self) -> str:
        listed = ", ".join(self.rejected[:_MAX_REJECTED_LISTED]) or _DROPPED_FALLBACK
        return _DROPPED_MESSAGE.format(rejected=listed)


class _Sanitizer:
    def __init__(self, summary: dict[str, Any]) -> None:
        self._item_types = _object_item_types(summary)
        self.rejected: list[str] = []

    def _reject(self, reasons: list[str]) -> None:
        self.rejected += [r for r in reasons if r not in self.rejected]

    def _length_violations(self, p_dict: dict[str, Any]) -> list[str]:
        target_type = str(p_dict.get("target_type") or "").strip()
        updates = p_dict.get("field_updates")
        if not isinstance(updates, dict):
            return []
        target_id = str(p_dict.get("target_id") or "").strip().upper()
        return length_violations(target_type, updates, self._item_types.get(target_id))

    def _clean_patch(self, p_dict: dict[str, Any]) -> Optional[FixProposalEntityPatch]:
        target_type = str(p_dict.get("target_type") or "").strip()
        field_updates = p_dict.get("field_updates") or {}
        if target_type not in _PATCH_TARGET_TYPES or not isinstance(field_updates, dict):
            self._reject([target_type or "?"])
            return None
        allowed = _allowed_fields_for(target_type)
        self._reject([f"{target_type}.{k}" for k in field_updates if k not in allowed])
        kept_updates = {str(k): v for k, v in field_updates.items() if k in allowed}
        if not kept_updates:
            return None
        target_id = p_dict.get("target_id")
        return FixProposalEntityPatch(
            target_type=target_type,  # type: ignore[arg-type]
            target_id=str(target_id).strip() if target_id is not None else None,
            description=str(p_dict.get("description") or "").strip()[:280],
            field_updates=kept_updates,
        )

    def clean_proposal(self, raw: Any) -> Optional[FixProposal]:
        raw_dict = _as_dict(raw)
        if raw_dict is None:
            return None
        title = str(raw_dict.get("title") or "").strip()
        summary_text = str(raw_dict.get("summary") or "").strip()
        if not title or not summary_text:
            return None
        raw_patches = [d for d in (_as_dict(x) for x in raw_dict.get("patches") or []) if d]
        too_long = [v for d in raw_patches for v in self._length_violations(d)]
        if too_long:
            # A shortened value would change the fix's meaning, so drop the whole option.
            self._reject(too_long)
            return None
        patches = [p for p in (self._clean_patch(d) for d in raw_patches) if p]
        if not patches:
            return None
        rationale = raw_dict.get("rationale")
        return FixProposal(
            title=title[:120],
            summary=summary_text[:600],
            rationale=(str(rationale).strip()[:400] if rationale else None),
            patches=patches,
        )


def sanitize_proposals(raw_proposals: list[Any], summary: dict[str, Any]) -> SanitizedProposals:
    """Clean raw LLM proposals against the allowlists and length limits of the world."""
    sanitizer = _Sanitizer(summary)
    proposals = [p for p in (sanitizer.clean_proposal(raw) for raw in raw_proposals) if p]
    return SanitizedProposals(proposals=proposals, rejected=sanitizer.rejected)
