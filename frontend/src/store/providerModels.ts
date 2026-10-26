import { reactive } from 'vue'
import { api } from '@/composables/useApi'
import type { ModelKind, ProviderModelList } from '@/composables/useApi'

export interface ProviderModelsEntry {
  status: 'loading' | 'ready' | 'error'
  list: ProviderModelList | null
  requestError: string
}

/** Shared cache of discovered models, keyed by kind, provider and endpoint. */
const entries = reactive<Record<string, ProviderModelsEntry>>({})
const inFlight = new Map<string, Promise<void>>()

export function providerModelsKey(provider: string, kind: ModelKind, baseUrl = ''): string {
  return `${kind}:${provider}:${baseUrl}`
}

export function getProviderModelsEntry(key: string): ProviderModelsEntry | undefined {
  return entries[key]
}

async function fetchInto(key: string, provider: string, kind: ModelKind, baseUrl: string, refresh: boolean): Promise<void> {
  entries[key] = { status: 'loading', list: entries[key]?.list ?? null, requestError: '' }
  try {
    const list = await api.getProviderModels(provider, kind, { baseUrl: baseUrl || undefined, refresh })
    entries[key] = { status: 'ready', list, requestError: '' }
  } catch (error: any) {
    entries[key] = { status: 'error', list: null, requestError: error?.message || 'Model list could not be loaded.' }
  }
}

/** Loads a model list once; `refresh` asks the backend to bypass its cache as well. */
export function loadProviderModels(
  provider: string,
  kind: ModelKind,
  options: { baseUrl?: string; refresh?: boolean } = {},
): Promise<void> {
  const baseUrl = options.baseUrl ?? ''
  const key = providerModelsKey(provider, kind, baseUrl)
  const running = inFlight.get(key)
  if (running) {
    return running
  }
  if (!options.refresh && entries[key]?.status === 'ready') {
    return Promise.resolve()
  }
  const task = fetchInto(key, provider, kind, baseUrl, Boolean(options.refresh)).finally(() => inFlight.delete(key))
  inFlight.set(key, task)
  return task
}

/** Drops cached lists for a provider, e.g. after its API key changed. */
export function invalidateProviderModels(provider: string): void {
  for (const key of Object.keys(entries)) {
    if (key.split(':')[1] === provider) {
      delete entries[key]
    }
  }
}
