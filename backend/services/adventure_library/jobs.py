"""In-process registry of adventure download jobs: download -> verify -> import.

Jobs live in memory only. They are short-lived progress records for the library dialog,
not durable state; a server restart simply forgets them (the ``.part`` file of an
interrupted download is cleaned up by the downloader or overwritten by the next attempt).

Each job runs as its own ``asyncio`` task. Concurrency is capped by
``settings.ADVENTURE_DOWNLOAD_CONCURRENCY`` and every job has a wall-clock deadline of
``settings.ADVENTURE_DOWNLOAD_JOB_TIMEOUT`` seconds (spec section 7, DoS).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import backend.core.database as core_database
from backend.core.config import settings
from backend.services.adventure_library.downloader import (
    AdventureDownloader,
    DownloadCancelledError,
    DownloadError,
    resolve_target_path,
)
from backend.services.adventure_library.installer import AdventureInstaller, AdventureInstallError
from backend.services.adventure_library.models import CatalogEntry, DownloadJob, JobState

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset({JobState.DONE, JobState.ERROR, JobState.CANCELLED})
# Terminal records older than this are dropped so a long-running server does not leak.
_RETENTION = timedelta(hours=1)
# States in which a cancel request is still honoured; importing is a DB transaction.
_CANCELLABLE_STATES = frozenset({JobState.QUEUED, JobState.DOWNLOADING, JobState.VERIFYING})


class JobError(Exception):
    """Request-level failure: unknown job id or a duplicate active job."""


@dataclass
class JobRecord:
    """Internal bookkeeping for one job; ``task`` is held to keep it from being GC'd."""

    job: DownloadJob
    owner_id: str
    entry: CatalogEntry
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_state(job: DownloadJob, state: JobState, error: str | None = None, **extra: Any) -> None:
    job.state = state
    job.error = error
    for name, value in extra.items():
        setattr(job, name, value)
    job.updated_at = _now()


def _is_active(record: JobRecord) -> bool:
    return record.job.state not in TERMINAL_STATES


class JobManager:
    """Starts, tracks and cancels download jobs, scoped per owner."""

    def __init__(
        self,
        downloader: AdventureDownloader | None = None,
        installer: AdventureInstaller | None = None,
    ) -> None:
        self._records: dict[str, JobRecord] = {}
        self._downloader = downloader or AdventureDownloader()
        self._installer = installer or AdventureInstaller()
        # Created lazily: there may be no running event loop at import time.
        self._semaphore: asyncio.Semaphore | None = None

    async def start(self, entry: CatalogEntry, owner_id: str) -> DownloadJob:
        """Register a job for ``entry`` and schedule it; return the live job object.

        Raises :class:`JobError` when a job for the same ``(slug, version)`` is still
        active, because both would write to the same ``.part`` file. Raises
        ``UnsafeDownloadTargetError`` up front when slug/version are unusable.
        """
        self._prune()
        if (entry.slug, entry.version) in self.active_keys():
            raise JobError(f"a download for {entry.slug} {entry.version} is already running")
        # Fail before scheduling: an unsafe target is a catalog defect, not a job error.
        resolve_target_path(entry.slug, entry.version, settings.adventure_download_dir)

        now = _now()
        job = DownloadJob(
            job_id=uuid.uuid4().hex,
            adventure_id=entry.id,
            slug=entry.slug,
            title=entry.title,
            version=entry.version,
            total_bytes=entry.size_bytes,
            created_at=now,
            updated_at=now,
        )
        record = JobRecord(job=job, owner_id=owner_id, entry=entry)
        self._records[job.job_id] = record
        record.task = asyncio.create_task(self._execute(record), name=f"adv-dl-{job.job_id}")
        return job

    def get(self, job_id: str, owner_id: str) -> DownloadJob | None:
        """Return the job when it exists and belongs to ``owner_id``."""
        record = self._records.get(job_id)
        if record is None or record.owner_id != owner_id:
            return None
        return record.job

    def list_for(self, owner_id: str) -> list[DownloadJob]:
        """Return the owner's jobs newest-first, after pruning expired terminal records."""
        self._prune()
        jobs = [record.job for record in self._records.values() if record.owner_id == owner_id]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def active_keys(self) -> set[tuple[str, str]]:
        """Return ``(slug, version)`` of every job that has not reached a terminal state."""
        return {
            (record.job.slug, record.job.version)
            for record in self._records.values()
            if _is_active(record)
        }

    def cancel(self, job_id: str, owner_id: str) -> bool:
        """Request cancellation; False for unknown, foreign, terminal or importing jobs."""
        record = self._records.get(job_id)
        if record is None or record.owner_id != owner_id:
            return False
        if record.job.state not in _CANCELLABLE_STATES:
            return False
        record.cancel_event.set()
        if record.job.state == JobState.QUEUED and record.task is not None:
            # Still waiting for a slot: stop waiting instead of holding the queue.
            record.task.cancel()
        return True

    async def shutdown(self) -> None:
        """Cancel every running job and wait for the tasks to unwind."""
        tasks = [record.task for record in self._records.values() if record.task]
        for record in self._records.values():
            record.cancel_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _semaphore_for_loop(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(max(1, settings.ADVENTURE_DOWNLOAD_CONCURRENCY))
        return self._semaphore

    def _prune(self) -> None:
        cutoff = _now() - _RETENTION
        expired = [
            job_id
            for job_id, record in self._records.items()
            if not _is_active(record) and record.job.updated_at < cutoff
        ]
        for job_id in expired:
            del self._records[job_id]

    async def _execute(self, record: JobRecord) -> None:
        """Task body: run the job under the per-job deadline and record the outcome.

        ``asyncio.wait_for`` is used instead of ``asyncio.timeout`` because the project
        still supports Python 3.10.
        """
        job = record.job
        try:
            await asyncio.wait_for(
                self._run(record), timeout=settings.ADVENTURE_DOWNLOAD_JOB_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Adventure download %s %s timed out", job.slug, job.version)
            _set_state(job, JobState.ERROR, "Download timed out")
            await self._remove_partial(record.entry)
        except asyncio.CancelledError:
            _set_state(job, JobState.CANCELLED, "Download cancelled")
            await self._remove_partial(record.entry)
            raise
        except DownloadCancelledError:
            _set_state(job, JobState.CANCELLED, "Download cancelled")
        except (DownloadError, AdventureInstallError) as exc:
            logger.warning("Adventure download %s %s failed: %s", job.slug, job.version, exc)
            _set_state(job, JobState.ERROR, str(exc) or exc.__class__.__name__)
        except Exception as exc:
            # Importer failures (conflicts, DB errors) end the job, never the server.
            logger.exception("Adventure install %s %s failed", job.slug, job.version)
            _set_state(job, JobState.ERROR, f"Import failed: {exc}")

    async def _run(self, record: JobRecord) -> None:
        async with self._semaphore_for_loop():
            path = await self._downloader.download(
                record.entry, job=record.job, cancel_event=record.cancel_event
            )
            # A cancel accepted during verification wins over the import.
            if record.cancel_event.is_set():
                raise DownloadCancelledError("download cancelled")
            # Synchronous with the check above, so cancel() cannot slip in between.
            _set_state(record.job, JobState.IMPORTING)
            # Own session: the request that started the job is long finished.
            async with core_database.AsyncSessionLocal() as db:
                template_id = await self._installer.install(db, path, owner_id=record.owner_id)
        _set_state(record.job, JobState.DONE, template_id=template_id)
        logger.info("Installed adventure %s %s", record.job.slug, record.job.version)

    async def _remove_partial(self, entry: CatalogEntry) -> None:
        try:
            target = resolve_target_path(entry.slug, entry.version, settings.adventure_download_dir)
        except DownloadError:
            return
        await self._downloader.cleanup_partial(target)


job_manager = JobManager()
