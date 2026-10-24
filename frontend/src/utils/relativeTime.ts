const RELATIVE_STEPS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/** Formats a timestamp as "3 days ago" / "just now". */
export function formatRelative(dateStr?: string | null): string {
  if (!dateStr) return 'recently'
  const seconds = (new Date(dateStr).getTime() - Date.now()) / 1000
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  const step = RELATIVE_STEPS.find(([, size]) => Math.abs(seconds) >= size)
  if (!step) return 'just now'
  return formatter.format(Math.round(seconds / step[1]), step[0])
}

/** Epoch millis of the last play, falling back to creation; 0 when neither is known. Used for sorting. */
export function lastPlayedMs(entry: { last_played_at?: string | null; created_at?: string }): number {
  const stamp = entry.last_played_at || entry.created_at
  return stamp ? new Date(stamp).getTime() : 0
}
