import { computed, getCurrentScope, onScopeDispose, ref, type ComputedRef, type Ref } from 'vue'
import { adventureLibraryService } from '@/services/adventureLibrary'
import type {
  AdventureCatalogResponse,
  AdventureDownloadJob,
  AdventureJobState,
  AdventureLibraryItem,
} from '@/types/adventureLibrary'

const POLL_MIN_MS = 1000
const POLL_MAX_MS = 5000
const ACTIVE_STATES: ReadonlySet<AdventureJobState> = new Set(['queued', 'downloading', 'verifying', 'importing'])

export interface UseAdventureLibraryResult {
  isOpen: Ref<boolean>
  items: Ref<AdventureLibraryItem[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  staleCatalog: Ref<boolean>
  selectedIds: Ref<Set<string>>
  selectedCount: ComputedRef<number>
  selectedTotalBytes: ComputedRef<number>
  catalogTotalBytes: ComputedRef<number>
  allSelectableSelected: ComputedRef<boolean>
  jobErrors: ComputedRef<string[]>
  isSubmitting: Ref<boolean>
  openDialog: () => Promise<void>
  closeDialog: () => void
  load: () => Promise<void>
  refresh: () => Promise<void>
  isSelectable: (item: AdventureLibraryItem) => boolean
  isSelected: (id: string) => boolean
  toggle: (id: string) => void
  selectAll: () => void
  clearSelection: () => void
  jobFor: (adventureId: string) => AdventureDownloadJob | undefined
  downloadSelected: () => Promise<void>
  cancel: (jobId: string) => Promise<void>
}

export function isActiveJob(job: AdventureDownloadJob): boolean {
  return ACTIVE_STATES.has(job.state)
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/** Owns the adventure library dialog: catalog, selection, download polling and errors. */
export function useAdventureLibrary(): UseAdventureLibraryResult {
  const isOpen = ref(false)
  const items = ref<AdventureLibraryItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const staleCatalog = ref(false)
  const selectedIds = ref<Set<string>>(new Set())
  const isSubmitting = ref(false)
  // Latest job per adventure id (the API lists jobs newest-first).
  const jobsByAdventure = ref<Map<string, AdventureDownloadJob>>(new Map())
  // Jobs started or observed running while this composable was alive; only their errors are shown.
  const trackedJobIds = ref<Set<string>>(new Set())

  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let pollInterval = POLL_MIN_MS
  // Incremented per loop; a tick from an older loop never reschedules (prevents two loops).
  let pollGeneration = 0
  let pollActive = false
  let lastProgressSignature = ''

  const selectedItems = computed(() => items.value.filter((item) => selectedIds.value.has(item.entry.id)))
  const selectedCount = computed(() => selectedItems.value.length)
  const selectedTotalBytes = computed(() => selectedItems.value.reduce((sum, item) => sum + item.entry.size_bytes, 0))
  const catalogTotalBytes = computed(() => items.value.reduce((sum, item) => sum + item.entry.size_bytes, 0))
  const selectableItems = computed(() => items.value.filter(isSelectable))
  const allSelectableSelected = computed(
    () => selectableItems.value.length > 0 && selectableItems.value.every((item) => selectedIds.value.has(item.entry.id)),
  )

  const jobErrors = computed(() =>
    [...jobsByAdventure.value.values()]
      .filter((job) => job.state === 'error' && trackedJobIds.value.has(job.job_id))
      .map((job) => `${job.title}: ${job.error || 'Download failed.'}`),
  )

  /** Single selection rule, shared by `selectAll()` and the card checkboxes. */
  function isSelectable(item: AdventureLibraryItem): boolean {
    return item.compatible === true && !item.downloading && item.installed_version !== item.entry.version
  }

  function isSelected(id: string): boolean {
    return selectedIds.value.has(id)
  }

  function toggle(id: string) {
    const item = items.value.find((candidate) => candidate.entry.id === id)
    const next = new Set(selectedIds.value)
    if (next.has(id)) {
      next.delete(id)
    } else if (item && isSelectable(item)) {
      next.add(id)
    }
    selectedIds.value = next
  }

  function selectAll() {
    selectedIds.value = new Set(selectableItems.value.map((item) => item.entry.id))
  }

  function clearSelection() {
    selectedIds.value = new Set()
  }

  /** Records the first failure only, so a broken poll loop does not overwrite the root cause. */
  function reportError(err: unknown, fallback: string) {
    if (error.value) {
      return
    }
    error.value = errorMessage(err, fallback)
  }

  function jobFor(adventureId: string): AdventureDownloadJob | undefined {
    return jobsByAdventure.value.get(adventureId)
  }

  function applyCatalog(response: AdventureCatalogResponse) {
    items.value = response.items
    staleCatalog.value = response.stale
    // Drop selections that are no longer selectable (installed, downloading, removed).
    const selectable = new Set(selectableItems.value.map((item) => item.entry.id))
    selectedIds.value = new Set([...selectedIds.value].filter((id) => selectable.has(id)))
    // Resume progress tracking for downloads started earlier (e.g. before the dialog was reopened).
    if (isOpen.value && items.value.some((item) => item.downloading)) {
      startPolling()
    }
  }

  async function fetchInto(fetcher: () => Promise<AdventureCatalogResponse>, fallback: string) {
    loading.value = true
    try {
      applyCatalog(await fetcher())
    } catch (err) {
      reportError(err, fallback)
    } finally {
      loading.value = false
    }
  }

  function load(): Promise<void> {
    return fetchInto(adventureLibraryService.fetchCatalog, 'Failed to load the adventure catalog.')
  }

  function refresh(): Promise<void> {
    error.value = null
    return fetchInto(adventureLibraryService.refreshCatalog, 'Failed to refresh the adventure catalog.')
  }

  /** Merges job progress into the per-adventure map and the items' `downloading` flag. */
  function applyJobs(jobs: AdventureDownloadJob[]) {
    const latest = new Map<string, AdventureDownloadJob>()
    for (const job of jobs) {
      if (!latest.has(job.adventure_id)) {
        latest.set(job.adventure_id, job)
      }
    }
    jobsByAdventure.value = latest

    const activeIds = jobs.filter(isActiveJob).map((job) => job.job_id)
    trackedJobIds.value = new Set([...trackedJobIds.value, ...activeIds])

    for (const item of items.value) {
      const job = latest.get(item.entry.id)
      item.downloading = job ? isActiveJob(job) : false
    }
  }

  function progressSignature(jobs: AdventureDownloadJob[]): string {
    return jobs.map((job) => `${job.job_id}:${job.state}:${job.bytes_downloaded}`).join('|')
  }

  function scheduleTick(generation: number, delay: number) {
    pollTimer = setTimeout(() => void pollJobs(generation), delay)
  }

  /** One poll round: fetch jobs, merge progress, then stop or reschedule with backoff. */
  async function pollJobs(generation: number) {
    pollTimer = null
    let jobs: AdventureDownloadJob[] | null = null
    try {
      jobs = (await adventureLibraryService.fetchJobs()).jobs
    } catch (err) {
      reportError(err, 'Failed to load download progress.')
    }
    if (!pollActive || generation !== pollGeneration) {
      return
    }
    if (jobs) {
      applyJobs(jobs)
    }
    if (jobs && !jobs.some(isActiveJob)) {
      stopPolling()
      // Every job is terminal: reload once so `installed_version` reflects the imports.
      await load()
      return
    }
    const signature = jobs ? progressSignature(jobs) : lastProgressSignature
    const progressed = signature !== lastProgressSignature
    lastProgressSignature = signature
    pollInterval = progressed ? POLL_MIN_MS : Math.min(pollInterval * 2, POLL_MAX_MS)
    scheduleTick(generation, pollInterval)
  }

  function startPolling() {
    pollInterval = POLL_MIN_MS
    if (pollActive) {
      return
    }
    pollActive = true
    pollGeneration += 1
    lastProgressSignature = ''
    scheduleTick(pollGeneration, POLL_MIN_MS)
  }

  function stopPolling() {
    pollActive = false
    pollGeneration += 1
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  async function downloadSelected() {
    const ids = selectedItems.value.filter(isSelectable).map((item) => item.entry.id)
    if (ids.length === 0 || isSubmitting.value) {
      return
    }
    error.value = null
    isSubmitting.value = true
    try {
      const { jobs } = await adventureLibraryService.startDownloads(ids)
      trackedJobIds.value = new Set([...trackedJobIds.value, ...jobs.map((job) => job.job_id)])
      const started = new Set(jobs.map((job) => job.adventure_id))
      items.value.filter((item) => started.has(item.entry.id)).forEach((item) => (item.downloading = true))
      clearSelection()
      startPolling()
    } catch (err) {
      reportError(err, 'Failed to start the download.')
    } finally {
      isSubmitting.value = false
    }
  }

  async function cancel(jobId: string) {
    try {
      await adventureLibraryService.cancelJob(jobId)
      startPolling()
    } catch (err) {
      reportError(err, 'Failed to cancel the download.')
    }
  }

  async function openDialog() {
    isOpen.value = true
    error.value = null
    await load()
  }

  /** Closes the dialog and stops polling; running downloads continue on the server. */
  function closeDialog() {
    isOpen.value = false
    stopPolling()
  }

  if (getCurrentScope()) {
    onScopeDispose(stopPolling)
  }

  return {
    isOpen,
    items,
    loading,
    error,
    staleCatalog,
    selectedIds,
    selectedCount,
    selectedTotalBytes,
    catalogTotalBytes,
    allSelectableSelected,
    jobErrors,
    isSubmitting,
    openDialog,
    closeDialog,
    load,
    refresh,
    isSelectable,
    isSelected,
    toggle,
    selectAll,
    clearSelection,
    jobFor,
    downloadSelected,
    cancel,
  }
}
