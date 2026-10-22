"""Repairs stale /data asset URLs that no longer point at an existing file."""

from __future__ import annotations

import glob
import os
from typing import Optional

from backend.core.config import settings
from backend.utils.path_security import (
    assert_within_data_dir,
    data_url_to_local_path,
    ensure_within_base_dir,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
    sanitize_relative_segment,
)

_PROFILE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_PROTAGONIST_MARKER = "PROTAGONIST"


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _is_servable(abs_path: str, data_root: str) -> bool:
    """True when the URL can stay as-is: an existing file inside the data dir.

    Paths that cannot be compared (e.g. different drives) are left untouched as well.
    """
    try:
        within = os.path.commonpath([abs_path, data_root]) == data_root
    except ValueError:
        return True
    return within and os.path.isfile(abs_path)


def _find_relocated_asset(filename: str, data_root: str) -> Optional[str]:
    """/data URL of a same-named file in the library or session folders, if any."""
    for bucket in ("library", "sessions"):
        root_abs = os.path.abspath(os.path.join(settings.DATA_DIR, "adventures", bucket))
        if not os.path.isdir(root_abs):
            continue
        for alt in glob.iglob(os.path.join(root_abs, "**", filename), recursive=True):
            alt_abs = os.path.abspath(alt)
            if _is_within(alt_abs, data_root) and os.path.isfile(alt_abs):
                rel_alt = os.path.relpath(alt_abs, data_root).replace("\\", "/")
                return f"/data/{rel_alt}"
    return None


def resolve_existing_data_asset_url(url: Optional[str]) -> Optional[str]:
    """Best-effort repair for stale /data URLs that no longer match current folders.

    Returns None when the file is gone and no replacement exists, so callers can fall
    back to alternative image sources rather than serving a 404.
    """
    if not isinstance(url, str):
        return url
    candidate = url.strip()
    abs_path = data_url_to_local_path(candidate) if candidate.startswith("/data/") else None
    data_root = os.path.abspath(settings.DATA_DIR)
    if not abs_path or _is_servable(abs_path, data_root):
        return candidate

    filename = os.path.basename(abs_path)
    if not filename:
        return candidate
    return _find_relocated_asset(filename, data_root)


def _protagonist_image_name(library_dir: str) -> Optional[str]:
    """Prefers ``PROTAGONIST.<ext>``, else the first image containing PROTAGONIST."""
    fuzzy_match = None
    with os.scandir(library_dir) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            if os.path.splitext(entry.name)[1].lower() not in _PROFILE_IMAGE_EXTENSIONS:
                continue
            name_upper = entry.name.upper()
            if name_upper.startswith(f"{_PROTAGONIST_MARKER}."):
                return entry.name
            if fuzzy_match is None and _PROTAGONIST_MARKER in name_upper:
                fuzzy_match = entry.name
    return fuzzy_match


def _library_image_url(library_dir: str, file_name: str) -> Optional[str]:
    safe_name = os.path.basename(sanitize_relative_segment(file_name) or "")
    if not safe_name:
        return None
    try:
        candidate = ensure_within_base_dir(os.path.join(library_dir, safe_name), library_dir)
        candidate = assert_within_data_dir(candidate)
    except ValueError:
        return None
    return local_path_to_data_url(candidate) if os.path.isfile(candidate) else None


def _library_protagonist_url(template_id: str) -> Optional[str]:
    try:
        library_dir = safe_data_path("adventures", "library", template_id)
    except ValueError:
        return None
    if not os.path.isdir(library_dir):
        return None
    try:
        file_name = _protagonist_image_name(library_dir)
    except OSError:
        return None
    return _library_image_url(library_dir, file_name) if file_name else None


def heal_template_avatar_profile_image(
    template_id: Optional[str], profile_image: Optional[str]
) -> Optional[str]:
    """Heals a template avatar image that points to a deleted session path."""
    if not template_id or not profile_image or "/adventures/sessions/" not in profile_image:
        return profile_image
    safe_template_id = sanitize_path_component(template_id)
    if not safe_template_id:
        return profile_image
    abs_path = data_url_to_local_path(profile_image)
    if abs_path and os.path.isfile(abs_path):
        return profile_image
    return _library_protagonist_url(safe_template_id) or profile_image
