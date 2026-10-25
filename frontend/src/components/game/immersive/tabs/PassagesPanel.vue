<script setup lang="ts">
/**
 * PassagesPanel — Exits of the current scene as route cards.
 */
import { DoorOpen, Lock, ArrowRight } from 'lucide-vue-next'

const props = defineProps<{
  sceneExits: any[]
  currentSceneName?: string | null
  isEvaluating?: boolean
}>()

const emit = defineEmits<{
  traverseExit: [exit: any]
}>()

function formatSceneTitle(name?: string | null): string {
  if (!name) return ''
  const trimmed = String(name).trim()
  if (trimmed.includes('_') || trimmed.includes('-') || /^[A-Z0-9\s_-]+$/.test(trimmed)) {
    return trimmed
      .replace(/[_-]+/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }
  return trimmed
}

function targetName(exit: any): string {
  return exit.target_scene_name || formatSceneTitle(exit.target_scene_id)
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <h3 class="tw-panel-title">Passages & Exits</h3>
      <span class="tw-muted text-[11px] font-bold">
        {{ props.sceneExits.length }} {{ props.sceneExits.length === 1 ? 'route' : 'routes' }}
      </span>
    </div>
    <p class="tw-muted text-xs leading-relaxed">Choose a route to leave this place. Locked passages need a key or a solution first.</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
      <button
        v-for="exit in props.sceneExits"
        :key="exit.id || exit.label"
        type="button"
        class="tw-card tw-card--interactive group flex items-center gap-3 p-3 text-left"
        :disabled="props.isEvaluating"
        :class="{ 'opacity-50 pointer-events-none': props.isEvaluating }"
        @click="emit('traverseExit', exit)"
      >
        <span
          class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border"
          :class="exit.is_locked ? 'bg-red-950/50 border-red-500/40 text-red-400' : 'bg-emerald-950/50 border-emerald-500/40 text-emerald-400'"
        >
          <Lock v-if="exit.is_locked" class="w-4 h-4" />
          <DoorOpen v-else class="w-4 h-4" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-bold truncate">{{ exit.label || 'Exit' }}</span>
          <span v-if="exit.target_scene_name || exit.target_scene_id" class="tw-muted flex items-center gap-1 text-[11px] truncate">
            <span class="truncate">{{ props.currentSceneName || 'Here' }}</span>
            <ArrowRight class="w-3 h-3 shrink-0" />
            <span class="truncate font-semibold">{{ targetName(exit) }}</span>
          </span>
        </span>
        <span
          class="shrink-0 text-[9px] font-black uppercase px-2 py-0.5 rounded-full border"
          :class="exit.is_locked ? 'bg-red-500/15 text-red-500 border-red-500/40' : 'bg-emerald-500/15 text-emerald-600 border-emerald-500/40'"
        >
          {{ exit.is_locked ? 'Locked' : 'Open' }}
        </span>
      </button>
    </div>
  </div>
</template>
