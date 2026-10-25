export type SessionSettingsPayload = {
  turns: number
  enableCompression: boolean
  autoSpeech: boolean
  autoSpeakNarration: boolean
  autoSpeakDialogues: boolean
  language: string
}

export type SettingsTabId = 'memory' | 'voice' | 'translation'
