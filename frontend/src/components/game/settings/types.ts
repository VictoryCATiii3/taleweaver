import type { SkinPreference } from '@/skins/skinRegistry'

export type SessionSettingsPayload = {
  turns: number
  enableCompression: boolean
  autoSpeech: boolean
  autoSpeakNarration: boolean
  autoSpeakDialogues: boolean
  language: string
  skin: SkinPreference
}

export type SettingsTabId = 'memory' | 'voice' | 'translation' | 'display'
