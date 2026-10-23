"""Hand a verified bundle to the existing importer and refresh the local scan cache.

Import logic is deliberately not re-implemented here: ``AdventureTemplateImporter``
already enforces the zip-bomb limits, manifest validation and conflict detection, and
the downloaded file lands in a directory ``scan_available_adventure_files`` already
covers (spec D4), so a cache refresh is all it takes to make it visible.
"""

from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.adventure_identity import manifest_origin_id
from backend.engine.adventure_import_support import find_existing_template, read_adz_manifest
from backend.engine.adventure_importer import AdventureTemplateImporter

logger = logging.getLogger(__name__)


class AdventureInstallError(Exception):
    """The importer rejected the bundle (invalid or unprocessable ``.adz``)."""


def _read_identity(data: bytes) -> tuple[str | None, str | None]:
    """Return ``(title, origin_id)`` from the bundle manifest, or ``(None, None)``."""
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zip_file:
            manifest = read_adz_manifest(zip_file)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        logger.debug("Could not read manifest identity: %s", exc)
        return None, None
    if not manifest:
        return None, None
    return (manifest.get("adventure") or {}).get("title"), manifest_origin_id(manifest)


class AdventureInstaller:
    """Imports a downloaded ``.adz`` into the owner's library."""

    async def install(
        self,
        db: AsyncSession,
        file_path: Path,
        *,
        owner_id: str,
        overwrite: bool = True,
    ) -> str | None:
        """Import ``file_path`` and return the resulting template id when resolvable.

        ``AdventureConflictError`` propagates unchanged so the API layer can map it to
        HTTP 409. A rejected bundle raises :class:`AdventureInstallError`.
        """
        data = await asyncio.to_thread(file_path.read_bytes)
        imported = await AdventureTemplateImporter.import_adz(
            db, data, owner_id=owner_id, overwrite=overwrite
        )
        if not imported:
            raise AdventureInstallError(f"importer rejected {file_path.name}")

        # Make the new file visible to the up-to-date checks immediately instead of
        # after the scan cache TTL; the scan walks the disk, so keep it off the loop.
        # Imported lazily: adventure_updates has an import cycle through the API
        # routers and cannot be imported before them.
        from backend.engine.adventure_updates import scan_available_adventure_files

        await asyncio.to_thread(scan_available_adventure_files, True)

        title, origin_id = _read_identity(data)
        if not title:
            return None
        template = await find_existing_template(db, owner_id, title, origin_id)
        return template.id if template else None
