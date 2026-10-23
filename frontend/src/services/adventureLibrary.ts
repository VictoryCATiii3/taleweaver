import { apiFetch, type ApiFetchInit } from '@/services/http'
import type {
  AdventureCatalogResponse,
  AdventureDownloadJob,
  AdventureJobsResponse,
} from '@/types/adventureLibrary'

const LIBRARY_PATH = '/adventures/library'
// Catalog calls may hit the remote catalog host, so allow more than the default timeout.
const CATALOG_TIMEOUT_MS = 30000

/** Error raised by the adventure library service; carries the HTTP status (0 = network). */
export class AdventureLibraryError extends Error {
  status: number
  detail: string | null

  constructor(status: number, message: string, detail: string | null = null) {
    super(message)
    this.name = 'AdventureLibraryError'
    this.status = status
    this.detail = detail
  }
}

/** Extracts a readable message from a FastAPI `detail` (string or validation error list). */
function detailToString(detail: unknown): string | null {
  if (typeof detail === 'string') {
    return detail
  }
  if (!Array.isArray(detail)) {
    return null
  }
  const messages = detail
    .map((item: unknown) => (item && typeof item === 'object' ? (item as { msg?: unknown }).msg : null))
    .filter((msg): msg is string => typeof msg === 'string')
  return messages.length > 0 ? messages.join('; ') : null
}

/** Reads the error body without assuming JSON (proxies may return HTML or plain text). */
async function readErrorDetail(res: Response): Promise<string | null> {
  const text = await res.text().catch(() => '')
  if (!text) {
    return null
  }
  try {
    const body: unknown = JSON.parse(text)
    const detail = body && typeof body === 'object' ? (body as { detail?: unknown }).detail : null
    return detailToString(detail)
  } catch {
    // Not JSON: only surface short plain-text bodies, never whole HTML pages.
    return text.length <= 200 && !text.trimStart().startsWith('<') ? text.trim() : null
  }
}

async function request<T>(path: string, fallbackMessage: string, init: ApiFetchInit = {}): Promise<T> {
  let res: Response
  try {
    res = await apiFetch(`${LIBRARY_PATH}${path}`, init)
  } catch {
    throw new AdventureLibraryError(0, `${fallbackMessage} (network error or timeout)`)
  }
  if (!res.ok) {
    const detail = await readErrorDetail(res)
    throw new AdventureLibraryError(res.status, detail ?? `${fallbackMessage} (HTTP ${res.status})`, detail)
  }
  return (await res.json()) as T
}

/**
 * Service for the adventure library: remote catalog browsing and download jobs.
 */
export const adventureLibraryService = {
  fetchCatalog(): Promise<AdventureCatalogResponse> {
    return request('/catalog', 'Failed to load the adventure catalog.', { timeoutMs: CATALOG_TIMEOUT_MS })
  },

  refreshCatalog(): Promise<AdventureCatalogResponse> {
    return request('/refresh', 'Failed to refresh the adventure catalog.', {
      method: 'POST',
      timeoutMs: CATALOG_TIMEOUT_MS,
    })
  },

  startDownloads(ids: string[]): Promise<AdventureJobsResponse> {
    return request('/download', 'Failed to start the download.', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify({ ids }),
      timeoutMs: CATALOG_TIMEOUT_MS,
    })
  },

  fetchJobs(): Promise<AdventureJobsResponse> {
    return request('/jobs', 'Failed to load download progress.')
  },

  cancelJob(jobId: string): Promise<AdventureDownloadJob> {
    return request(`/jobs/${encodeURIComponent(jobId)}/cancel`, 'Failed to cancel the download.', {
      method: 'POST',
    })
  },
}
