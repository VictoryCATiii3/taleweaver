import type { SkinPreference } from '@/skins/skinRegistry'
import type { TextDensity } from '@/skins/useTextDensity'

export type SessionSettingsPayload = {
  turns: number
  enableCompression: boolean
  autoSpeech: boolean
  autoSpeakNarration: boolean
  autoSpeakDialogues: boolean
  language: string
  skin: SkinPreference
  density: TextDensity
}

export type SettingsTabId = 'memory' | 'voice' | 'translation' | 'display'
