import { computed, reactive } from 'vue'
import { api } from '@/composables/useApi'
import type { SetupWizardState } from '@/composables/useApi'
import { authState } from '@/store/auth'
import { configState } from '@/store/config'

export type SetupArea = 'llm' | 'visuals'

/**
 * Setup wizard state for admins (global settings are admin-only).
 *
 * - `pending`: never handled; the wizard opens automatically while setup is incomplete.
 * - `skipped`: closed for now; the nav button stays while setup is incomplete.
 * - `dismissed`: hidden for good (re-enable from the admin settings).
 * - `completed`: finished the wizard.
 */
export const setupWizardState = reactive({
  isLoaded: false,
  isOpen: false,
  state: 'pending' as SetupWizardState,
  visualsOptOut: false,
})

export const isSetupWizardAvailable = computed((): boolean => authState.user?.role === 'admin')

/** Areas still unconfigured; LLM covers API keys, since a cloud LLM requires one. */
export const missingSetupAreas = computed((): SetupArea[] => {
  if (!configState.isLoaded) {
    return []
  }
  const missing: SetupArea[] = []
  if (!configState.hasLlmConfig) {
    missing.push('llm')
  }
  if (!configState.hasT2iConfig && !setupWizardState.visualsOptOut) {
    missing.push('visuals')
  }
  return missing
})

export const showSetupWizardButton = computed((): boolean => {
  if (!isSetupWizardAvailable.value || !setupWizardState.isLoaded) {
    return false
  }
  return setupWizardState.state !== 'dismissed' && missingSetupAreas.value.length > 0
})

/** Loads the wizard state once per login and opens it for a fresh, incomplete setup. */
export async function loadSetupWizard(): Promise<void> {
  if (!isSetupWizardAvailable.value || setupWizardState.isLoaded) {
    return
  }
  try {
    const status = await api.getSetupWizard()
    setupWizardState.state = status.state
    setupWizardState.visualsOptOut = status.visuals_opt_out
    setupWizardState.isLoaded = true
  } catch (error) {
    console.error('[SetupWizard] Failed to load state:', error)
    return
  }
  if (setupWizardState.state === 'pending' && missingSetupAreas.value.length > 0) {
    setupWizardState.isOpen = true
  }
}

export function resetSetupWizard(): void {
  setupWizardState.isLoaded = false
  setupWizardState.isOpen = false
}

export function openSetupWizard(): void {
  setupWizardState.isOpen = true
}

async function persist(payload: { state?: SetupWizardState; visuals_opt_out?: boolean }): Promise<void> {
  try {
    const status = await api.updateSetupWizard(payload)
    setupWizardState.state = status.state
    setupWizardState.visualsOptOut = status.visuals_opt_out
  } catch (error) {
    console.error('[SetupWizard] Failed to save state:', error)
  }
}

/** Closes the wizard and records why: finished, skipped for now, or hidden for good. */
export async function closeSetupWizard(state: SetupWizardState): Promise<void> {
  setupWizardState.isOpen = false
  await persist({ state })
}

export async function setVisualsOptOut(optOut: boolean): Promise<void> {
  await persist({ visuals_opt_out: optOut })
}

/** Opens the wizard from the admin settings, bringing it back if it was dismissed. */
export async function restartSetupWizard(): Promise<void> {
  if (setupWizardState.state === 'dismissed') {
    await persist({ state: 'skipped' })
  }
  openSetupWizard()
}
