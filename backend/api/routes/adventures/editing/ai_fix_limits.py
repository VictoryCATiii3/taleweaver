"""Field length limits shared by AI fix suggestion filtering and patch application.

Mirrors the editor's own save limits (``entity_update/*`` and the adventure
update schema) so proposals the editor would reject are filtered out before
the user ever sees them, and the LLM is told about them up front.
"""

from typing import Any, Optional

READABLE_DESCRIPTION_MAX = 200
TEXT_LOG_CONTENT_MAX = 1000
DECORATIVE_OBJECT_MAX = 100

_FIELD_LIMITS: dict[tuple[str, str], int] = {
    ("object", "text_log_content"): TEXT_LOG_CONTENT_MAX,
    ("adventure", "title"): 50,
    ("adventure", "teaser"): 300,
    ("adventure", "plot"): 5000,
    ("adventure", "rules"): 5000,
    ("adventure", "tts_director_notes"): 5000,
    ("adventure", "intro_text"): 20000,
    ("adventure", "completed_condition"): 2000,
    ("adventure", "gameover_condition"): 2000,
}


def max_length(target_type: str, field: str, item_type: Optional[str] = None) -> Optional[int]:
    """Character limit for ``target_type.field`` (None when unlimited)."""
    is_readable = str(item_type or "").upper() == "READABLE"
    if target_type == "object" and field == "description" and is_readable:
        return READABLE_DESCRIPTION_MAX
    return _FIELD_LIMITS.get((target_type, field))


def _decor_violation(target_type: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    longest = max((len(str(v).strip()) for v in value), default=0)
    if longest <= DECORATIVE_OBJECT_MAX:
        return []
    return [
        f"{target_type}.decorative_objects entry is {longest} chars (max {DECORATIVE_OBJECT_MAX})"
    ]


def length_violations(
    target_type: str, field_updates: dict[str, Any], item_type: Optional[str] = None
) -> list[str]:
    """Human-readable descriptions of every field value that exceeds its limit."""
    violations: list[str] = []
    for field, value in field_updates.items():
        if field == "decorative_objects":
            violations += _decor_violation(target_type, value)
            continue
        limit = max_length(target_type, field, item_type)
        length = len(value.strip()) if isinstance(value, str) else 0
        if limit is not None and length > limit:
            violations.append(f"{target_type}.{field} is {length} chars (max {limit})")
    return violations


def format_length_limits() -> str:
    """Prompt section listing the hard limits the LLM must respect."""
    lines = [f"    - {t}.{f}: {limit}" for (t, f), limit in _FIELD_LIMITS.items()]
    lines += [
        f"    - object.description of READABLE objects: {READABLE_DESCRIPTION_MAX}",
        f"    - each scene.decorative_objects entry: {DECORATIVE_OBJECT_MAX}",
    ]
    return (
        "\nFIELD LENGTH LIMITS (characters, hard limits; proposals exceeding them are discarded)\n"
        + "\n".join(lines)
        + "\n- When shortening is needed, rewrite the text concisely instead of truncating it.\n"
    )
