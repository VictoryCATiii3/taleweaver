"""Stable adventure identity (``origin_id``).

The ``origin_id`` identifies an adventure across exports, imports and updates, independent
of its title. It is owned by the system: generated when an adventure is created, copied or
covered, written to the ``adventure`` section on export, and preserved on import/update.
"""

import uuid
from typing import Any, Optional


def new_origin_id() -> str:
    """Generates a fresh, globally unique adventure identity."""
    return str(uuid.uuid4())


def manifest_origin_id(manifest: Any) -> Optional[str]:
    """Reads the stable ID from the manifest's ``adventure`` section.

    Top-level ``origin_id`` values are ignored: older LLM-generated manifests used that key
    for the starting scene, so it is not a reliable identity.
    """
    if not isinstance(manifest, dict):
        return None
    section = manifest.get("adventure")
    if not isinstance(section, dict):
        return None
    value = str(section.get("origin_id") or "").strip()
    return value or None
