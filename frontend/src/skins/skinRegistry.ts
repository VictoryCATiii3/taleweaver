/**
 * Dialog skins for the immersive game view.
 *
 * A skin is a set of CSS design tokens plus a few structural rules (see skins/*.css),
 * applied through `data-skin` on the immersive root. Components only use the semantic
 * `tw-*` classes, so adding a skin never requires touching component markup.
 */

export const SKIN_IDS = ['classic', 'chronicle', 'noir', 'terminal', 'grimoire', 'eldritch', 'toon'] as const

export type SkinId = (typeof SKIN_IDS)[number]

/** Player preference: a concrete skin, or follow the adventure. */
export type SkinPreference = SkinId | 'auto'

export type SkinDefinition = {
  id: SkinId
  label: string
  description: string
  /** Swatch colors for the settings picker: [background, ink, accent]. */
  swatch: [string, string, string]
}

/** Author-defined theme stored on the adventure (validated server-side). */
export type AdventureUiTheme = {
  skin?: string | null
  accent?: string | null
}

export const SKINS: SkinDefinition[] = [
  {
    id: 'classic',
    label: 'Classic',
    description: 'The original TaleWeaver comic look with glowing bubbles.',
    swatch: ['#0f172a', '#f1f5f9', '#f59e0b'],
  },
  {
    id: 'chronicle',
    label: 'Chronicle',
    description: 'Illuminated parchment, drop caps and ribbon banners.',
    swatch: ['#eadcbc', '#2b1d0e', '#8a2b1a'],
  },
  {
    id: 'noir',
    label: 'Noir',
    description: 'Typewritten case files and hard-boiled dialogue cards.',
    swatch: ['#ebe4d1', '#1d1b17', '#c8102e'],
  },
  {
    id: 'terminal',
    label: 'Terminal',
    description: 'Holographic panels, scanlines and monospace readouts.',
    swatch: ['#04131a', '#c7f9ff', '#22d3ee'],
  },
  {
    id: 'grimoire',
    label: 'Grimoire',
    description: 'Dark vellum, blood-red ink and candlelit edges.',
    swatch: ['#16100e', '#e8dccb', '#b91c1c'],
  },
  {
    id: 'eldritch',
    label: 'Eldritch',
    description: 'Murky darkness, sickly green glow and a flickering lamp.',
    swatch: ['#070b07', '#d6e5cf', '#a3e635'],
  },
  {
    id: 'toon',
    label: 'Toon',
    description: 'Loud cartoon panels, bouncy bubbles and halftone dots.',
    swatch: ['#fffbea', '#111111', '#f97316'],
  },
]

/** Keyword (lower case) found in the adventure tone → skin. First match wins. */
const TONE_KEYWORDS: [string, SkinId][] = [
  ['cyberpunk', 'terminal'],
  ['sci-fi', 'terminal'],
  ['scifi', 'terminal'],
  ['science', 'terminal'],
  ['space', 'terminal'],
  ['noir', 'noir'],
  ['mystery', 'noir'],
  ['detective', 'noir'],
  ['crime', 'noir'],
  ['slapstick', 'toon'],
  ['comedy', 'toon'],
  ['satir', 'toon'],
  ['funny', 'toon'],
  ['humor', 'toon'],
  ['humour', 'toon'],
  ['parody', 'toon'],
  ['cartoon', 'toon'],
  ['horror', 'eldritch'],
  ['cosmic', 'eldritch'],
  ['lovecraft', 'eldritch'],
  ['eldritch', 'eldritch'],
  ['zombie', 'eldritch'],
  ['grimdark', 'grimoire'],
  ['gothic', 'grimoire'],
  ['dark', 'grimoire'],
  ['heroic', 'chronicle'],
  ['fantasy', 'chronicle'],
  ['whimsical', 'chronicle'],
  ['fairy', 'chronicle'],
  ['epic', 'chronicle'],
  ['medieval', 'chronicle'],
]

const HEX_COLOR = /^#[0-9a-f]{6}$/i

export function isSkinId(value: unknown): value is SkinId {
  return typeof value === 'string' && (SKIN_IDS as readonly string[]).includes(value)
}

export function findSkin(id: SkinId): SkinDefinition {
  return SKINS.find((skin) => skin.id === id) ?? SKINS[0]
}

/** Accepts the tone as stored on the sheet: a string or a catalog tile `{ id, name }`. */
export function toneLabel(tone: unknown): string {
  if (typeof tone === 'string') {
    return tone
  }
  if (!tone || typeof tone !== 'object') {
    return ''
  }
  const tile = tone as { id?: unknown; name?: unknown }
  const label = [tile.name, tile.id].find((part) => typeof part === 'string' && part.trim())
  return typeof label === 'string' ? label : ''
}

function toneSearchText(tone: unknown): string {
  if (!tone || typeof tone !== 'object') {
    return toneLabel(tone).toLowerCase()
  }
  const tile = tone as { id?: unknown; name?: unknown }
  return [tile.name, tile.id]
    .filter((part) => typeof part === 'string')
    .join(' ')
    .toLowerCase()
}

export function skinForTone(tone: unknown): SkinId {
  const label = toneSearchText(tone)
  if (!label) {
    return 'classic'
  }
  const match = TONE_KEYWORDS.find(([keyword]) => label.includes(keyword))
  return match ? match[1] : 'classic'
}

/** Player preference → adventure author's choice → tone mapping → classic. */
export function resolveSkin(
  preference: SkinPreference,
  theme: AdventureUiTheme | null | undefined,
  tone: unknown,
): SkinId {
  if (preference !== 'auto') {
    return preference
  }
  if (isSkinId(theme?.skin)) {
    return theme.skin
  }
  return skinForTone(tone)
}

/** Human-readable reason for the skin "Auto" resolves to (settings dialog). */
export function describeAutoSkin(theme: AdventureUiTheme | null | undefined, tone: unknown): string {
  if (isSkinId(theme?.skin)) {
    return 'chosen by the adventure author'
  }
  const label = toneLabel(tone).trim()
  if (!label) {
    return 'no tone set, using the default look'
  }
  return skinForTone(tone) === 'classic' ? `no skin matches the tone "${label}"` : `matches the tone "${label}"`
}

/** Author accent override; ignored when the player picked a skin explicitly. */
export function resolveAccent(
  preference: SkinPreference,
  theme: AdventureUiTheme | null | undefined,
): string | null {
  if (preference !== 'auto') {
    return null
  }
  const accent = theme?.accent
  return typeof accent === 'string' && HEX_COLOR.test(accent) ? accent : null
}
