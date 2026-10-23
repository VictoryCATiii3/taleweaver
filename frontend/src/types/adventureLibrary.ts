/**
 * Adventure library API contract.
 * Mirrors backend/services/adventure_library/models.py and
 * backend/api/routes/adventures/library.py.
 */

/** One downloadable adventure as described by the remote catalog (`CatalogEntry`). */
export interface AdventureCatalogEntry {
  id: string
  slug: string
  title: string
  teaser: string
  description: string
  version: string
  format_version: string
  released_at: string | null
  min_app_version: string
  size_bytes: number
  sha256: string
  download_url: string
  cover_url: string | null
  cover_sha256: string | null
  tags: string[]
  author: string
  license: string
  language: string
}

/** A catalog entry merged with the caller's install and download state (`CatalogItemView`). */
export interface AdventureLibraryItem {
  entry: AdventureCatalogEntry
  installed_version: string | null
  update_available: boolean
  downloading: boolean
  compatible: boolean
  requires_app_version: string | null
}

export type AdventureJobState =
  | 'queued'
  | 'downloading'
  | 'verifying'
  | 'importing'
  | 'done'
  | 'error'
  | 'cancelled'

/** Progress record of one download (`DownloadJob`). */
export interface AdventureDownloadJob {
  job_id: string
  adventure_id: string
  slug: string
  title: string
  version: string
  state: AdventureJobState
  bytes_downloaded: number
  total_bytes: number
  error: string | null
  template_id: string | null
  created_at: string
  updated_at: string
}

/** Response of `GET /library/catalog` and `POST /library/refresh`. */
export interface AdventureCatalogResponse {
  items: AdventureLibraryItem[]
  catalog_generated_at: string | null
  stale: boolean
}

/** Response of `POST /library/download` and `GET /library/jobs`. */
export interface AdventureJobsResponse {
  jobs: AdventureDownloadJob[]
}
