"""Streamed, verified download of catalog bundles into the adventure download directory.

Security rules implemented here (spec section 7):

- SSRF (CWE-918): only ``https`` URLs on the allowlisted hosts are contacted, and
  redirects are followed manually so every hop is re-validated. An automatic redirect
  could otherwise bounce an allowlisted URL to an internal address.
- Path traversal (CWE-22): the target filename is derived from the catalog slug and
  version through a strict charset, never from the URL or a response header, and the
  resolved path must stay inside the download directory.
- Disk fill: ``size_bytes`` is checked against the cap before the request and the byte
  count is enforced while streaming, so a lying server cannot write more than announced.
- Supply chain: the sha256 is computed while streaming and compared in constant time
  with the catalog value; nothing becomes visible under the final name before it matches.

The bundle is never unpacked or inspected here; that is the importer's job.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

import httpx

from backend.core.config import settings
from backend.services.adventure_library.models import CatalogEntry, DownloadJob, JobState
from backend.services.adventure_library.url_policy import http_client, url_rejection_reason

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5
PART_SUFFIX = ".part"

_SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_VERSION_RE = re.compile(r"[A-Za-z0-9._+-]+")
_MAX_NAME_PART = 64
# Per-operation timeouts; the overall per-job deadline is enforced by the job service.
_DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class DownloadError(Exception):
    """Base class for every download failure."""


class DownloadCancelledError(DownloadError):
    """The download was cancelled through its cancel event."""


class HashMismatchError(DownloadError):
    """The downloaded bytes do not match the catalog sha256 or size."""


class UnsafeDownloadTargetError(DownloadError):
    """Slug/version would produce an unsafe filename or a path outside the target dir."""


def safe_target_name(slug: str, version: str) -> str:
    """Build ``<slug>-<version>.adz`` from strictly validated components.

    The charsets exclude path separators, NUL and whitespace, so the result is always a
    single path component; this is the first CWE-22 barrier.
    """
    if len(slug) > _MAX_NAME_PART or not _SLUG_RE.fullmatch(slug):
        raise UnsafeDownloadTargetError(f"unsafe adventure slug {slug!r}")
    if len(version) > _MAX_NAME_PART or not _VERSION_RE.fullmatch(version):
        raise UnsafeDownloadTargetError(f"unsafe adventure version {version!r}")
    return f"{slug}-{version}.adz"


def resolve_target_path(slug: str, version: str, download_dir: str) -> Path:
    """Return the absolute target path and assert it stays inside ``download_dir``.

    Containment is checked on the resolved paths (symlinks included) as the second,
    independent CWE-22 barrier in case the name validation is ever loosened.
    """
    base = Path(download_dir).resolve()
    target = (base / safe_target_name(slug, version)).resolve()
    if not target.is_relative_to(base) or target == base:
        raise UnsafeDownloadTargetError(f"download target escapes {base}")
    return target


def _part_path(target: Path) -> Path:
    return (
        target if target.name.endswith(PART_SUFFIX) else target.with_name(target.name + PART_SUFFIX)
    )


def _require_allowed_url(url: str) -> None:
    reason = url_rejection_reason(url)
    if reason:
        raise DownloadError(f"refusing to download {url!r}: {reason}")


def _update_job(job: DownloadJob | None, **changes: Any) -> None:
    if job is None:
        return
    for name, value in changes.items():
        setattr(job, name, value)
    job.updated_at = datetime.now(timezone.utc)


def _raise_if_cancelled(cancel_event: asyncio.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelledError("download cancelled")


class _StreamSink:
    """Writes chunks to the ``.part`` file while hashing and enforcing the byte limit."""

    def __init__(self, handle: IO[bytes], limit: int, on_progress: Callable[[int], None]) -> None:
        self._handle = handle
        self._limit = limit
        self._on_progress = on_progress
        self.hasher = hashlib.sha256()
        self.received = 0

    def write(self, chunk: bytes) -> None:
        self.received += len(chunk)
        # Abort before writing: the limit is min(announced size, global cap), so a
        # server sending more than the catalog promised is cut off immediately.
        if self.received > self._limit:
            raise HashMismatchError(f"stream exceeded the expected {self._limit} bytes")
        self.hasher.update(chunk)
        self._handle.write(chunk)
        self._on_progress(self.received)


class AdventureDownloader:
    """Downloads one catalog entry to ``settings.adventure_download_dir``."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

    async def download(
        self,
        entry: CatalogEntry,
        *,
        job: DownloadJob | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> Path:
        """Download, verify and atomically publish the bundle; return its final path."""
        _require_allowed_url(entry.download_url)
        cap = settings.ADVENTURE_DOWNLOAD_MAX_BYTES
        if entry.size_bytes > cap:
            raise DownloadError(f"bundle size {entry.size_bytes} exceeds the {cap} byte cap")

        target = resolve_target_path(entry.slug, entry.version, settings.adventure_download_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = _part_path(target)
        _update_job(
            job, state=JobState.DOWNLOADING, bytes_downloaded=0, total_bytes=entry.size_bytes
        )

        try:
            _raise_if_cancelled(cancel_event)
            sink = await self._stream_to_part(
                entry, part, min(entry.size_bytes, cap), job, cancel_event
            )
            _update_job(job, state=JobState.VERIFYING)
            _verify(entry, sink)
            os.replace(part, target)
        except DownloadCancelledError:
            await self.cleanup_partial(target)
            _update_job(job, state=JobState.CANCELLED, error="Download cancelled")
            raise
        except BaseException as exc:
            # BaseException also covers asyncio.CancelledError / task timeouts, which
            # must not leave a half-written .part file behind either.
            await self.cleanup_partial(target)
            _update_job(job, state=JobState.ERROR, error=str(exc) or exc.__class__.__name__)
            raise
        logger.info("Downloaded adventure %s %s to %s", entry.slug, entry.version, target)
        return target

    async def cleanup_partial(self, target: Path) -> None:
        """Remove the ``.part`` file belonging to ``target``; a missing file is fine."""
        try:
            _part_path(target).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove partial download %s: %s", target, exc)

    async def _stream_to_part(
        self,
        entry: CatalogEntry,
        part: Path,
        limit: int,
        job: DownloadJob | None,
        cancel_event: asyncio.Event | None,
    ) -> _StreamSink:
        async with http_client(self._http_client, _DOWNLOAD_TIMEOUT) as client:
            response = await self._open_stream(client, entry.download_url)
            try:
                return await _save_stream(response, part, limit, job, cancel_event)
            finally:
                await response.aclose()

    async def _open_stream(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Send a streaming GET, following up to MAX_REDIRECTS redirects manually.

        ``follow_redirects=False`` is passed per request so even an injected client
        configured to follow redirects cannot skip the per-hop allowlist check.
        """
        for _ in range(MAX_REDIRECTS + 1):
            _require_allowed_url(url)
            request = client.build_request("GET", url)
            response = await client.send(request, stream=True, follow_redirects=False)
            if not response.is_redirect:
                return response
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                raise DownloadError("redirect without Location header")
            url = str(response.url.join(location))
        raise DownloadError(f"more than {MAX_REDIRECTS} redirects")


def _check_response(response: httpx.Response, limit: int) -> None:
    """Reject non-200 answers and announced lengths above the limit before reading."""
    if response.status_code != httpx.codes.OK:
        raise DownloadError(f"unexpected HTTP status {response.status_code}")
    announced = response.headers.get("content-length", "")
    if announced.isdigit() and int(announced) > limit:
        raise HashMismatchError(f"server announced {announced} bytes, expected at most {limit}")


async def _save_stream(
    response: httpx.Response,
    part: Path,
    limit: int,
    job: DownloadJob | None,
    cancel_event: asyncio.Event | None,
) -> _StreamSink:
    """Stream the body into ``part``; the cancel event is checked between chunks."""
    _check_response(response, limit)
    with part.open("wb") as handle:
        sink = _StreamSink(handle, limit, lambda n: _update_job(job, bytes_downloaded=n))
        async for chunk in response.aiter_bytes(CHUNK_SIZE):
            _raise_if_cancelled(cancel_event)
            sink.write(chunk)
    return sink


def _verify(entry: CatalogEntry, sink: _StreamSink) -> None:
    """Fail loudly unless size and sha256 both match the catalog (spec D7)."""
    if sink.received != entry.size_bytes:
        raise HashMismatchError(f"received {sink.received} bytes, catalog says {entry.size_bytes}")
    if not hmac.compare_digest(sink.hasher.hexdigest(), entry.sha256.lower()):
        raise HashMismatchError(f"sha256 mismatch for {entry.slug} {entry.version}")
