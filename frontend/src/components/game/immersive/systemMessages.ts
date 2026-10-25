/**
 * Classification helpers for system messages shown in the story feed and the System tab.
 */
import type { ChatMessage } from '@/types'

export type TurnError = { message: string; action: string } | null | undefined

type SystemMessage = Pick<ChatMessage, 'content'> & { is_debug?: boolean }

export function isDebugMessage(msg: SystemMessage | null | undefined): boolean {
  if (msg?.is_debug) {
    return true
  }
  const content = String(msg?.content || '').trim()
  return content.startsWith('[DEBUG') || content.startsWith('DEBUG:') || content.startsWith('--- DEBUG')
}

/** Failed-turn announcements stay inline in the story because they carry Retry/Cancel actions. */
export function isTurnErrorMessage(msg: SystemMessage | null | undefined, turnError: TurnError): boolean {
  return Boolean(turnError?.message && String(msg?.content || '').includes(turnError.message))
}

/** Removes inline debug trigger markers from regular system messages. */
export function cleanSystemContent(msg: SystemMessage | null | undefined): string {
  const content = String(msg?.content || '')
  if (isDebugMessage(msg)) {
    return content
  }
  return content
    .replace(/\s*\[DEBUG:\s*Trigger fired\][^\n]*/gi, '')
    .replace(/\s*\[DEBUG\][^\n]*/gi, '')
    .trim()
}
