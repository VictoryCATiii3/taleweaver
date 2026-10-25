<script setup lang="ts">
/**
 * SettingCard — Labelled settings block with an explanation text,
 * an optional "how it works" hint, and a slot for the control.
 */
const props = defineProps<{
  title: string
  description: string
  hint?: string
  badge?: string
  badgeTone?: 'amber' | 'blue' | 'cyan'
  disabled?: boolean
}>()

const BADGE_TONES = {
  amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  blue: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
}
</script>

<template>
  <section
    class="rounded-2xl border border-white/10 bg-white/[0.03] p-4 transition-opacity"
    :class="{ 'opacity-50': props.disabled }"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0 space-y-1">
        <div class="flex flex-wrap items-center gap-2">
          <h4 class="text-xs font-black uppercase tracking-widest text-slate-100">{{ props.title }}</h4>
          <span
            v-if="props.badge"
            class="rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-wider"
            :class="BADGE_TONES[props.badgeTone ?? 'amber']"
          >
            {{ props.badge }}
          </span>
        </div>
        <p class="text-xs leading-relaxed text-slate-400">{{ props.description }}</p>
      </div>
      <slot name="control" />
    </div>
    <slot />
    <p
      v-if="props.hint"
      class="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-slate-500"
    >
      <span class="font-bold uppercase tracking-wider text-slate-400">How it works · </span>{{ props.hint }}
    </p>
  </section>
</template>
