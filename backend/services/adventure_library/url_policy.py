"""Outbound URL policy and HTTP client handling shared by the catalog and the downloader.

Every URL the adventure library contacts originates from configuration or from the
remote catalog, never from an API caller. The catalog itself is remote data, though, so
each URL is still checked against a strict policy before a request is made (SSRF,
CWE-918): ``https`` only, default port only, no embedded credentials, and a host from
``settings.adventure_catalog_allowed_hosts``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx

from backend.core.config import settings


def url_rejection_reason(url: str) -> str | None:
    """Return why ``url`` must not be contacted, or ``None`` when it is allowed.

    - ``https`` only: a plain-http hop could be tampered with in transit, which would
      defeat the integrity guarantees of the catalog (there is deliberately no opt-out).
    - default port only: an allowlisted host on an unusual port is not the public
      service we trust.
    - no userinfo: ``https://github.com@evil.example/`` style URLs confuse humans
      reading logs; the parsed hostname is what counts and credentials are never sent.
    - host allowlist: blocks requests to internal services (cloud metadata endpoints,
      localhost admin ports) even if a catalog entry were crafted to point there.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "malformed URL"
    if parts.scheme.lower() != "https":
        return f"scheme {parts.scheme or '<none>'!r} is not https"
    if parts.username or parts.password:
        return "URL must not carry credentials"
    if port not in (None, 443):
        return f"port {port} is not allowed"
    host = (parts.hostname or "").lower()
    if host not in settings.adventure_catalog_allowed_hosts:
        return f"host {host or '<none>'!r} is not in the adventure library allowlist"
    return None


def is_allowed_url(url: str | None) -> bool:
    """Return True when ``url`` satisfies :func:`url_rejection_reason`."""
    return bool(url) and url_rejection_reason(url) is None


@asynccontextmanager
async def http_client(
    injected: httpx.AsyncClient | None, timeout: httpx.Timeout
) -> AsyncIterator[httpx.AsyncClient]:
    """Yield the injected client (owned by the caller) or a short-lived private one.

    Private clients never follow redirects automatically; callers that need redirects
    must follow them manually so every hop passes :func:`url_rejection_reason`.
    """
    if injected is not None:
        yield injected
        return
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        yield client
