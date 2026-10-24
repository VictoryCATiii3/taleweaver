/**
 * Maps an adventure tone (genre) to an accent color used for chips, buttons and glows.
 * Colors are exposed as space-separated RGB triplets so CSS can apply custom alpha values.
 */

export interface GenreAccent {
  key: string
  rgb: string
  icon: string
}

const DEFAULT_ACCENT: GenreAccent = { key: 'default', rgb: '78 222 163', icon: 'ra-scroll-unfurled' }

// Ordered: the first matching keyword wins, so more specific tones come first.
const ACCENT_RULES: ReadonlyArray<{ keywords: string[]; accent: GenreAccent }> = [
  { keywords: ['cosmic'], accent: { key: 'cosmic', rgb: '167 139 250', icon: 'ra-eye-monster' } },
  { keywords: ['horror'], accent: { key: 'horror', rgb: '248 113 113', icon: 'ra-skull' } },
  { keywords: ['sci', 'cyber', 'space'], accent: { key: 'scifi', rgb: '34 211 238', icon: 'ra-satellite' } },
  { keywords: ['absurd', 'slapstick', 'sitcom'], accent: { key: 'comedy', rgb: '244 114 182', icon: 'ra-perspective-dice-random' } },
  { keywords: ['rpg', 'heroic', 'epic'], accent: { key: 'heroic', rgb: '251 191 36', icon: 'ra-crossed-swords' } },
  { keywords: ['noir', 'detective'], accent: { key: 'noir', rgb: '203 213 225', icon: 'ra-fedora' } },
  { keywords: ['apocalyp', 'despair'], accent: { key: 'wasteland', rgb: '251 146 60', icon: 'ra-radioactive' } },
  { keywords: ['cozy', 'whimsical'], accent: { key: 'cozy', rgb: '163 230 53', icon: 'ra-flower' } },
  { keywords: ['melanchol', 'somber'], accent: { key: 'somber', rgb: '129 140 248', icon: 'ra-raven' } },
  { keywords: ['intrigue', 'political'], accent: { key: 'intrigue', rgb: '232 121 249', icon: 'ra-crown' } },
]

/** Resolves the accent for a tone label; unknown or empty tones fall back to the app's emerald. */
export function resolveGenreAccent(toneLabel: string | null | undefined): GenreAccent {
  if (!toneLabel) return DEFAULT_ACCENT
  const normalized = toneLabel.toLowerCase()
  const rule = ACCENT_RULES.find((entry) => entry.keywords.some((keyword) => normalized.includes(keyword)))
  return rule ? rule.accent : DEFAULT_ACCENT
}

/** Extracts a display label from the loosely typed `selected_tone` field. */
export function toneToLabel(tone: unknown): string {
  if (!tone) return ''
  if (typeof tone === 'object') {
    const tile = tone as { name?: string; id?: string }
    return tile.name || tile.id || ''
  }
  const text = String(tone)
  if (!text.startsWith('{')) return text
  try {
    const parsed = JSON.parse(text) as { name?: string; id?: string }
    return parsed.name || parsed.id || text
  } catch {
    return text
  }
}
