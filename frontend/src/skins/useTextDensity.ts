import { ref, watch } from 'vue'

export const TEXT_DENSITIES = ['compact', 'comfortable', 'spacious'] as const

export type TextDensity = (typeof TEXT_DENSITIES)[number]

export type TextDensityOption = {
  id: TextDensity
  label: string
  description: string
}

export const TEXT_DENSITY_OPTIONS: TextDensityOption[] = [
  {
    id: 'compact',
    label: 'Compact',
    description: 'Smaller text and tight spacing. More of the story fits on screen.',
  },
  {
    id: 'comfortable',
    label: 'Comfortable',
    description: 'Balanced size and spacing. The default.',
  },
  {
    id: 'spacious',
    label: 'Spacious',
    description: 'Larger text and generous spacing for relaxed reading.',
  },
]

const STORAGE_KEY = 'tw_text_density'

function isTextDensity(value: unknown): value is TextDensity {
  return typeof value === 'string' && (TEXT_DENSITIES as readonly string[]).includes(value)
}

function readDensity(): TextDensity {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return isTextDensity(stored) ? stored : 'comfortable'
  } catch {
    return 'comfortable'
  }
}

// Shared across components: the settings dialog writes, the immersive view reads.
const textDensity = ref<TextDensity>(readDensity())

watch(textDensity, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* storage unavailable (private mode) */
  }
})

export function useTextDensity() {
  return { textDensity }
}
