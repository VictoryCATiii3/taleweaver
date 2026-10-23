"""Adventure library API: browse the remote catalog and download adventures from it.

SSRF boundary (CWE-918, spec D6): no endpoint accepts a URL from the client. Requests
carry catalog entry ids only; the download URL is resolved server-side from the catalog,
which itself is fetched from ``settings.ADVENTURE_CATALOG_URL`` alone.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library import (
    AdventureCatalog,
    CatalogEntry,
    CatalogItemView,
    CatalogService,
    DownloadError,
    HashMismatchError,
    UnsafeDownloadTargetError,
    is_version_at_least,
)
from backend.services.adventure_library.jobs import JobError, job_manager

router = APIRouter(tags=["Adventures"])
logger = logging.getLogger(__name__)

_catalog_service = CatalogService()
# Upper bound per request; the catalog holds tens of entries, not thousands.
_MAX_IDS_PER_REQUEST = 200


class LibraryDownloadRequest(BaseModel):
    """Catalog ids to download; never URLs."""

    ids: list[str] = Field(min_length=1, max_length=_MAX_IDS_PER_REQUEST)


@contextmanager
def _service_errors() -> Iterator[None]:
    """Map adventure library service exceptions to HTTP errors."""
    try:
        yield
    except JobError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except UnsafeDownloadTargetError as exc:
        # The slug/version came from the catalog, so this is a catalog defect.
        logger.error("Catalog entry produced an unsafe download target: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except (HashMismatchError, DownloadError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.warning("Adventure catalog unavailable: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "catalog unavailable") from exc


async def _installed_versions(
    db: AsyncSession, owner_id: str, origin_ids: list[str]
) -> dict[str, str | None]:
    """Map ``origin_id`` -> highest installed version, in a single query.

    Scoped to the owner exactly like the template listing in ``templates.py``.
    """
    if not origin_ids:
        return {}
    result = await db.execute(
        select(AdventureTemplate.origin_id, AdventureTemplate.version).where(
            AdventureTemplate.owner_id == owner_id,
            AdventureTemplate.origin_id.in_(origin_ids),
        )
    )
    installed: dict[str, str | None] = {}
    for origin_id, version in result.all():
        current = installed.get(origin_id)
        if current is None or is_version_at_least(version or "", current):
            installed[origin_id] = version
    return installed


def _item_view(
    entry: CatalogEntry,
    installed_version: str | None,
    active_keys: set[tuple[str, str]],
) -> CatalogItemView:
    compatible = is_version_at_least(settings.APP_VERSION, entry.min_app_version)
    update_available = (
        installed_version is not None
        and entry.version != installed_version
        and is_version_at_least(entry.version, installed_version)
    )
    return CatalogItemView(
        entry=entry,
        installed_version=installed_version,
        update_available=update_available,
        downloading=(entry.slug, entry.version) in active_keys,
        compatible=compatible,
        requires_app_version=None if compatible else entry.min_app_version,
    )


async def _catalog_response(
    catalog: AdventureCatalog, db: AsyncSession, owner_id: str
) -> dict[str, Any]:
    """Merge the catalog with local install and job state (shared by catalog + refresh)."""
    installed = await _installed_versions(db, owner_id, [e.id for e in catalog.adventures])
    active_keys = job_manager.active_keys()
    items = [_item_view(e, installed.get(e.id), active_keys) for e in catalog.adventures]
    items.sort(key=lambda item: item.entry.title.casefold())
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "catalog_generated_at": catalog.generated_at,
        "stale": _catalog_service.is_stale(),
    }


def _resolve_entries(catalog: AdventureCatalog, ids: list[str]) -> list[CatalogEntry]:
    """Resolve ids to catalog entries; 404 for unknown ids, 409 for incompatible ones."""
    unique_ids = list(dict.fromkeys(ids))
    entries = {i: _catalog_service.resolve_entry(catalog, i) for i in unique_ids}
    unknown = [i for i, entry in entries.items() if entry is None]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown catalog id(s): {', '.join(unknown)}"
        )
    resolved = [entry for entry in entries.values() if entry is not None]
    incompatible = [
        f"{entry.title} requires app >= {entry.min_app_version}"
        for entry in resolved
        if not is_version_at_least(settings.APP_VERSION, entry.min_app_version)
    ]
    if incompatible:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Incompatible with app {settings.APP_VERSION}: {'; '.join(incompatible)}",
        )
    return resolved


def _reject_running(entries: list[CatalogEntry]) -> None:
    """409 before starting anything, so a request never starts only half its jobs."""
    active_keys = job_manager.active_keys()
    running = [e.title for e in entries if (e.slug, e.version) in active_keys]
    if running:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already downloading: {', '.join(running)}")


@router.get("/library/catalog")
async def get_library_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return catalog entries merged with the caller's install and download state."""
    with _service_errors():
        catalog = await _catalog_service.get_catalog()
    return await _catalog_response(catalog, db, current_user.id)


@router.post("/library/refresh")
async def refresh_library_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Bypass the catalog cache, then return the same view as ``GET /library/catalog``."""
    with _service_errors():
        catalog = await _catalog_service.refresh()
    return await _catalog_response(catalog, db, current_user.id)


@router.post("/library/download")
async def download_library_adventures(
    payload: LibraryDownloadRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Start one download job per catalog id."""
    with _service_errors():
        catalog = await _catalog_service.get_catalog()
    entries = _resolve_entries(catalog, payload.ids)
    _reject_running(entries)

    jobs = []
    with _service_errors():
        for entry in entries:
            jobs.append(await job_manager.start(entry, current_user.id))
    return {"jobs": [job.model_dump(mode="json") for job in jobs]}


@router.get("/library/jobs")
async def list_library_jobs(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the caller's jobs newest-first, including byte progress."""
    jobs = job_manager.list_for(current_user.id)
    return {"jobs": [job.model_dump(mode="json") for job in jobs]}


@router.post("/library/jobs/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_library_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Request cancellation of a queued or running download."""
    job = job_manager.get(job_id, current_user.id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if not job_manager.cancel(job_id, current_user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Job cannot be cancelled in state '{job.state.value}'"
        )
    return job.model_dump(mode="json")
