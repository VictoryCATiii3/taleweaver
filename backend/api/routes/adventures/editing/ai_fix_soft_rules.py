"""Sequence soft rules in AI fix suggestions: prompt context and flat-key patches.

Patch values must stay primitive, so a soft rule field is addressed with a flat key
``soft_rules.<RULE_ID>.<field>`` (e.g. ``soft_rules.BRENDA_FLIRT.guard_expression``).
Only existing rules can be patched; the AI never creates or deletes rules.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from backend.engine.scripting.sandbox import SafeAstInterpreter

SOFT_RULE_KEY_PREFIX = "soft_rules."
SOFT_RULE_FIELDS = frozenset({"condition", "script", "text", "guard_expression", "max_triggers"})
# Optional parts where an empty value means "remove"; a rule always keeps its condition.
_CLEARABLE_SOFT_RULE_FIELDS = SOFT_RULE_FIELDS - {"condition"}
_SCRIPT_CONTEXT_LIMIT = 400


def parse_soft_rule_key(key: str) -> Optional[tuple[str, str]]:
    """Returns (rule_id, field) for a ``soft_rules.<RULE_ID>.<field>`` key, else None."""
    if not key.startswith(SOFT_RULE_KEY_PREFIX):
        return None
    rule_id, _, field = key[len(SOFT_RULE_KEY_PREFIX) :].rpartition(".")
    return (rule_id, field) if rule_id and field in SOFT_RULE_FIELDS else None


def is_clearable_soft_rule_key(key: str) -> bool:
    parsed = parse_soft_rule_key(key)
    return parsed is not None and parsed[1] in _CLEARABLE_SOFT_RULE_FIELDS


def soft_rules_context(rules: Any) -> list[dict[str, Any]]:
    """Compact soft rule rows for the AI fix sequence context."""
    rows = [r for r in rules if isinstance(r, dict)] if isinstance(rules, list) else []
    return [
        {
            "id": r.get("id"),
            "condition": r.get("condition") or "",
            "guard_expression": r.get("guard_expression") or "",
            "max_triggers": r.get("max_triggers"),
            "text": r.get("text") or "",
            "script": str(r.get("script") or "")[:_SCRIPT_CONTEXT_LIMIT],
        }
        for r in rows
    ]


def _validated(field: str, value: Any) -> Any:
    if field == "max_triggers":
        count = int(value) if str(value).strip().lstrip("-").isdigit() else 0
        return count if count > 0 else None
    text = str(value).strip()
    if field == "condition" and not text:
        raise HTTPException(status_code=400, detail="A soft rule condition cannot be empty.")
    if field == "guard_expression" and text:
        errors = SafeAstInterpreter.check_expression_syntax(text)
    elif field == "script" and text:
        errors = SafeAstInterpreter.check_syntax(text)
    else:
        errors = []
    if errors:
        raise HTTPException(status_code=400, detail=f"Invalid soft rule {field}: {errors[0]}")
    return text


def apply_soft_rule_updates(sequence: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Returns ``sequence`` with the flat-key soft rule updates applied."""
    rules = [dict(r) for r in sequence.get("soft_rules") or [] if isinstance(r, dict)]
    index_by_id = {str(r.get("id") or "").strip().upper(): i for i, r in enumerate(rules)}
    for key, value in updates.items():
        rule_id, field = parse_soft_rule_key(key) or ("", "")
        idx = index_by_id.get(rule_id.strip().upper())
        if idx is None:
            # ``ai_fix_apply`` treats "could not be resolved" as a stale cached proposal.
            raise HTTPException(
                status_code=400,
                detail=f"soft rule '{rule_id}' could not be resolved in this adventure. "
                "The AI reference is stale; please retry.",
            )
        rules[idx][field] = _validated(field, value)
    return {**sequence, "soft_rules": rules}
