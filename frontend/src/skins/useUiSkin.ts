import { ref, watch } from 'vue'
import { isSkinId, type SkinPreference } from './skinRegistry'

const STORAGE_KEY = 'tw_ui_skin'

function readPreference(): SkinPreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return isSkinId(stored) ? stored : 'auto'
  } catch {
    return 'auto'
  }
}

// Shared across components: the settings dialog writes, the immersive view reads.
const skinPreference = ref<SkinPreference>(readPreference())

watch(skinPreference, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* storage unavailable (private mode) */
  }
})

export function useUiSkin() {
  return { skinPreference }
}
