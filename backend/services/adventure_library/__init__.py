"""Adventure library: discover, download, verify and install adventures from the catalog."""

from backend.services.adventure_library.catalog import (
    SUPPORTED_CATALOG_SCHEMA,
    CatalogError,
    CatalogService,
    load_snapshot,
    parse_catalog,
)
from backend.services.adventure_library.downloader import (
    AdventureDownloader,
    DownloadCancelledError,
    DownloadError,
    HashMismatchError,
    UnsafeDownloadTargetError,
    resolve_target_path,
    safe_target_name,
)
from backend.services.adventure_library.installer import AdventureInstaller, AdventureInstallError
from backend.services.adventure_library.models import (
    AdventureCatalog,
    CatalogEntry,
    CatalogItemView,
    DownloadJob,
    JobState,
    is_version_at_least,
    version_tuple,
)
from backend.services.adventure_library.url_policy import is_allowed_url, url_rejection_reason

__all__ = [
    "SUPPORTED_CATALOG_SCHEMA",
    "AdventureCatalog",
    "AdventureDownloader",
    "AdventureInstallError",
    "AdventureInstaller",
    "CatalogEntry",
    "CatalogError",
    "CatalogItemView",
    "CatalogService",
    "DownloadCancelledError",
    "DownloadError",
    "DownloadJob",
    "HashMismatchError",
    "JobState",
    "UnsafeDownloadTargetError",
    "is_allowed_url",
    "is_version_at_least",
    "load_snapshot",
    "parse_catalog",
    "resolve_target_path",
    "safe_target_name",
    "url_rejection_reason",
    "version_tuple",
]
