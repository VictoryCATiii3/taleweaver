export type BableFishLanguage = {
  /** Value sent to the backend; empty string keeps the adventure's original language. */
  code: string
  name: string
  short: string
  icon: string
}

export const BABLE_FISH_LANGUAGES: BableFishLanguage[] = [
  { code: '', name: 'Default', short: '—', icon: 'ra-spear-head' },
  { code: 'German', name: 'Deutsch', short: 'DE', icon: 'ra-castle' },
  { code: 'English', name: 'English', short: 'EN', icon: 'ra-tower' },
  { code: 'French', name: 'Français', short: 'FR', icon: 'ra-fleur-de-lis' },
  { code: 'Spanish', name: 'Español', short: 'ES', icon: 'ra-shield' },
  { code: 'Italian', name: 'Italiano', short: 'IT', icon: 'ra-scroll-unfurled' },
  { code: 'Japanese', name: '日本語', short: 'JA', icon: 'ra-shinto-shrine' },
  { code: 'Chinese', name: '中文', short: 'ZH', icon: 'ra-dragon' },
  { code: 'Russian', name: 'Русский', short: 'RU', icon: 'ra-hammer' },
  { code: 'Portuguese', name: 'Português', short: 'PT', icon: 'ra-anchor' },
]

export function findBableFishLanguage(code: string): BableFishLanguage | undefined {
  return BABLE_FISH_LANGUAGES.find((lang) => lang.code === code)
}
