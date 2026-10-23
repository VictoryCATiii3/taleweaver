"""Pydantic models for the adventure library: remote catalog, entries and download jobs."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"

_LEADING_NUMBER = re.compile(r"^\d+")


class CatalogEntry(BaseModel):
    """One downloadable adventure as described by ``catalog.json`` (schema 1)."""

    # Unknown fields are ignored so newer catalogs stay readable (spec section 4).
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, description="adventure.origin_id (UUID), primary key")
    slug: str = Field(pattern=SLUG_PATTERN, max_length=64)
    title: str = Field(min_length=1)
    teaser: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=2000)
    version: str = Field(min_length=1)
    format_version: str = "1.3"
    released_at: datetime | None = None
    min_app_version: str = "0.0.0"
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=SHA256_PATTERN)
    download_url: str
    cover_url: str | None = None
    cover_sha256: str | None = None
    tags: list[str] = Field(default_factory=list)
    author: str = ""
    license: str = ""
    language: str = ""


class AdventureCatalog(BaseModel):
    """The whole catalog document.

    The JSON key ``schema`` is exposed as ``schema_`` because ``schema`` would shadow a
    ``BaseModel`` attribute; dump with ``by_alias=True`` to get the wire format back.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schema_: int = Field(alias="schema")
    generated_at: datetime | None = None
    generator: str = ""
    adventures: list[CatalogEntry] = Field(default_factory=list)


class JobState(str, Enum):
    """Lifecycle of a single download job."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    IMPORTING = "importing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class DownloadJob(BaseModel):
    """Progress record of one download; mutated in place by the download service."""

    job_id: str
    adventure_id: str
    slug: str
    title: str
    version: str
    state: JobState = JobState.QUEUED
    bytes_downloaded: int = 0
    total_bytes: int = 0
    error: str | None = None
    template_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CatalogItemView(BaseModel):
    """A catalog entry merged with the local install state (API view)."""

    entry: CatalogEntry
    installed_version: str | None = None
    update_available: bool = False
    downloading: bool = False
    compatible: bool = True
    requires_app_version: str | None = None


def version_tuple(value: str) -> tuple[int, ...]:
    """Parse a dotted version into integers, ignoring non-numeric suffixes.

    ``"0.7.0-beta"`` -> ``(0, 7, 0)``; ``"1.2rc1"`` -> ``(1, 2)``; garbage -> ``(0,)``.
    """
    parts: list[int] = []
    for segment in (value or "").strip().split("."):
        match = _LEADING_NUMBER.match(segment)
        if not match:
            break
        parts.append(int(match.group()))
        if match.end() != len(segment):
            break
    return tuple(parts) if parts else (0,)


def _padded(parts: tuple[int, ...], length: int) -> tuple[int, ...]:
    return parts + (0,) * (length - len(parts))


def is_version_at_least(current: str, required: str) -> bool:
    """Return True when ``current`` >= ``required`` (missing components count as 0)."""
    current_parts = version_tuple(current)
    required_parts = version_tuple(required)
    length = max(len(current_parts), len(required_parts))
    return _padded(current_parts, length) >= _padded(required_parts, length)
