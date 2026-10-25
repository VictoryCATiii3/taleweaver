<script setup lang="ts">
/**
 * SystemLogPanel — Engine events of the session (dice rolls, rule checks, triggers,
 * item and stat changes), newest first. Entries that arrived since the tab was last
 * opened are highlighted.
 */
import { computed } from 'vue'
import type { ChatMessage } from '@/types'
import { renderFormattedHtml } from '@/composables/useComicTurns'
import { cleanSystemContent, isDebugMessage, isTurnErrorMessage, type TurnError } from '../systemMessages'
import DiceBadge from '../dice/DiceBadge.vue'
import { parseDiceRoll } from '../dice/diceRolls'

const props = defineProps<{
  messages: ChatMessage[]
  /** Number of messages the player had already seen when opening the tab. */
  seenCount: number
  turnError?: TurnError
}>()

type LogKind = 'system' | 'debug' | 'error'

const KIND_STYLES: Record<LogKind, { label: string; badge: string }> = {
  system: { label: 'System', badge: 'bg-emerald-500/15 text-emerald-500 border-emerald-500/40' },
  debug: { label: 'Debug', badge: 'bg-cyan-500/15 text-cyan-500 border-cyan-500/40' },
  error: { label: 'Error', badge: 'bg-red-500/15 text-red-500 border-red-500/40' },
}

const entries = computed(() =>
  props.messages
    .map((msg, index) => ({
      key: msg.id || `sys-${index}`,
      kind: kindOf(msg),
      html: renderFormattedHtml(cleanSystemContent(msg)),
      roll: parseDiceRoll(cleanSystemContent(msg)),
      time: formatTime(msg.timestamp),
      isNew: index >= props.seenCount,
    }))
    .reverse()
)

function kindOf(msg: ChatMessage): LogKind {
  if (isTurnErrorMessage(msg, props.turnError)) {
    return 'error'
  }
  return isDebugMessage(msg) ? 'debug' : 'system'
}

function formatTime(value: Date | string | undefined): string {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <h3 class="tw-panel-title">System Log</h3>
      <span class="tw-muted text-[11px] font-bold">{{ props.messages.length }} entries</span>
    </div>
    <p class="tw-muted text-xs leading-relaxed">
      Dice rolls, rule checks, triggers and changes to your character, newest first. They are kept here so the
      story stays readable.
    </p>

    <ol class="flex flex-col gap-2">
      <li
        v-for="entry in entries"
        :key="entry.key"
        class="tw-card p-3 text-xs sm:text-sm leading-relaxed"
        :class="{ 'ring-1 ring-[var(--tw-accent)]': entry.isNew }"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="px-1.5 py-0.5 rounded border text-[9px] font-black uppercase tracking-wider" :class="KIND_STYLES[entry.kind].badge">
            {{ KIND_STYLES[entry.kind].label }}
          </span>
          <span v-if="entry.isNew" class="text-[9px] font-black uppercase tracking-wider" style="color: var(--tw-accent)">New</span>
          <span v-if="entry.time" class="tw-muted ml-auto text-[10px] tabular-nums">{{ entry.time }}</span>
        </div>
        <div class="flex items-center gap-3">
          <DiceBadge
            v-if="entry.roll"
            still
            :value="entry.roll.value"
            :sides="entry.roll.sides"
            :is-crit="entry.roll.isCrit"
            :is-fumble="entry.roll.isFumble"
          />
          <p
            class="min-w-0 whitespace-pre-wrap break-words"
            :class="{ 'font-mono text-xs': entry.kind === 'debug' }"
            v-html="entry.html"
          ></p>
        </div>
      </li>
    </ol>
  </div>
</template>
