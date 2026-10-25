/**
 * Detects die rolls in engine system messages so they can be shown with a die graphic.
 *
 * Formats (backend): `/roll` → "🎲 **ROLL d6**: **4**" (backend/engine/dice_command.py),
 * skill checks → "Roll: 14 + 2 = **16** (vs DC 12) -> **SUCCESS**",
 * attacks → "To-Hit: 14 + 3 = **17** ... -> **HIT**", special attacks → "STR roll: 14 + 3 = ...".
 */

export type RollOutcome = 'success' | 'failure' | null

export type DiceRoll = {
  value: number
  sides: number
  outcome: RollOutcome
  isCrit: boolean
  isFumble: boolean
}

type RollPattern = { pattern: RegExp; sides: (match: RegExpMatchArray) => number; value: (match: RegExpMatchArray) => number }

const D20 = () => 20

const ROLL_PATTERNS: RollPattern[] = [
  { pattern: /ROLL d(\d+)\*\*:\s*\*\*(\d+)\*\*/i, sides: (m) => Number(m[1]), value: (m) => Number(m[2]) },
  { pattern: /\bTo-Hit:\s*(\d+)\s*[+-]/i, sides: D20, value: (m) => Number(m[1]) },
  { pattern: /\broll:\s*(\d+)\s*[+-]/i, sides: D20, value: (m) => Number(m[1]) },
]

function outcomeOf(content: string): RollOutcome {
  if (/\*\*(SUCCESS|HIT)\*\*/i.test(content)) {
    return 'success'
  }
  if (/\*\*(FAILURE|MISS)\*\*/i.test(content)) {
    return 'failure'
  }
  return null
}

export function parseDiceRoll(content: string): DiceRoll | null {
  for (const { pattern, sides, value } of ROLL_PATTERNS) {
    const match = content.match(pattern)
    if (!match) {
      continue
    }
    const dieSides = sides(match)
    const rolled = value(match)
    if (!dieSides || rolled < 1 || rolled > dieSides) {
      return null
    }
    return {
      value: rolled,
      sides: dieSides,
      outcome: outcomeOf(content),
      isCrit: rolled === dieSides,
      isFumble: rolled === 1,
    }
  }
  return null
}

/** The /roll message carries its result in the die graphic; drop the emoji prefix for display. */
export function stripDiceEmoji(content: string): string {
  return content.replace(/^\s*🎲\s*/u, '')
}
