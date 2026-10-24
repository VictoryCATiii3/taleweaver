<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { GameSession } from '@/types'
import { FileText, Play } from 'lucide-vue-next'
import ProgressRing from './ProgressRing.vue'
import TaleCardArtwork from './TaleCardArtwork.vue'
import SessionCardMenu, { type SessionCardAction } from './SessionCardMenu.vue'
import { useCardTilt } from '@/composables/useCardTilt'
import { resolveGenreAccent, toneToLabel } from '@/composables/useGenreAccent'
import { setAmbientAccent } from '@/store/portalAmbient'
import { formatRelative } from '@/utils/relativeTime'

const props = defineProps<{
  session: GameSession
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'copy', gameId: string): void
  (e: 'edit-note', gameId: string, currentNote: string): void
  (e: 'export', gameId: string): void
}>()

interface StatusView {
  label: string
  /** Wax seal for finished journeys; running ones get a small chip instead. */
  seal: boolean
  chipClass: string
  icon: string
  action: string
}

const STATUS_VIEWS: Record<string, StatusView> = {
  active: { label: 'Active', seal: false, chipClass: 'bg-slate-950/80 text-emerald-300 border-emerald-400/40', icon: 'ra-hourglass', action: 'Resume' },
  paused: { label: 'Paused', seal: false, chipClass: 'bg-slate-950/80 text-amber-300 border-amber-400/40', icon: 'ra-hourglass', action: 'Resume' },
  archived: { label: 'Archived', seal: false, chipClass: 'bg-slate-950/80 text-slate-300 border-slate-400/40', icon: 'ra-book', action: 'Open' },
  completed: { label: 'Victory', seal: true, chipClass: 'seal-victory', icon: 'ra-trophy', action: 'Revisit' },
  game_over: { label: 'Defeated', seal: true, chipClass: 'seal-defeat', icon: 'ra-skull', action: 'Revisit' },
}

const isMenuOpen = ref(false)
const isNoteOpen = ref(false)
const noteRef = ref<HTMLElement | null>(null)
const { tiltRef, onPointerMove, onPointerLeave } = useCardTilt()

const toneLabel = computed(() => toneToLabel(props.session.selected_tone))
const accent = computed(() => resolveGenreAccent(toneLabel.value))

const statusKey = computed(() => {
  const status = props.session.status
  if (status && status !== 'active') return status
  return props.session.is_paused ? 'paused' : 'active'
})
const statusView = computed(() => STATUS_VIEWS[statusKey.value] || STATUS_VIEWS.active)

const playtime = computed(() => {
  const extra = props.session as GameSession & { time_system?: string; time_config?: { unit_name?: string } }
  const unit = extra.time_system === 'units' ? extra.time_config?.unit_name || 'units' : 'min'
  return `${props.session.in_game_time || 0} ${unit}`
})

const relativeLastPlayed = computed(() => formatRelative(props.session.last_played_at || props.session.created_at))
const absoluteStart = computed(() =>
  props.session.created_at ? new Date(props.session.created_at).toLocaleString() : ''
)

const actionHandlers: Record<SessionCardAction, () => void> = {
  copy: () => emit('copy', props.session.game_id),
  'edit-note': () => emit('edit-note', props.session.game_id, props.session.status_note || ''),
  export: () => emit('export', props.session.game_id),
  delete: () => emit('delete', props.session.game_id, props.session.adventure_title),
}

function handleNoteClickOutside(event: MouseEvent): void {
  if (noteRef.value && !noteRef.value.contains(event.target as Node)) {
    isNoteOpen.value = false
  }
}

onMounted(() => window.addEventListener('mousedown', handleNoteClickOutside))
onUnmounted(() => window.removeEventListener('mousedown', handleNoteClickOutside))
</script>

<template>
  <article
    ref="tiltRef"
    class="tale-card group rounded-2xl aspect-[2/3] flex flex-col"
    :class="isMenuOpen || isNoteOpen ? 'z-30' : 'z-0'"
    :style="{ '--accent-rgb': accent.rgb }"
    @pointerenter="setAmbientAccent(accent.rgb)"
    @pointermove="onPointerMove"
    @pointerleave="onPointerLeave"
  >
    <TaleCardArtwork :image-url="props.session.image_url" :accent="accent" :muted="statusKey === 'game_over'" />

    <!-- Top row: status + note + options -->
    <!-- z-20: its menu and popups overlap the bottom block, which must stay underneath -->
    <div class="relative z-20 flex items-start justify-between gap-2 p-2 sm:p-3">
      <div class="flex flex-col gap-1.5 items-start min-w-0">
        <span
          v-if="!statusView.seal"
          class="px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border text-[9px] sm:text-[11px] font-bold tracking-wide flex items-center gap-1.5 backdrop-blur-md"
          :class="statusView.chipClass"
        >
          <span v-if="statusKey === 'active'" class="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse"></span>
          <i v-else :class="['ra', statusView.icon]" class="text-[10px]"></i>
          {{ statusView.label }}
        </span>
        <span
          v-if="toneLabel"
          class="tale-chip hidden sm:flex px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wide items-center gap-1.5 max-w-full"
          :title="toneLabel"
        >
          <i :class="['ra', accent.icon]" class="text-xs"></i>
          <span class="truncate">{{ toneLabel }}</span>
        </span>
        <span
          v-if="props.session.is_legacy_format"
          class="group/legacy relative px-2 py-0.5 sm:py-1 rounded-full bg-slate-950/80 text-rose-300 text-[9px] sm:text-[11px] font-bold border border-rose-500/40 flex items-center gap-1.5 backdrop-blur-md cursor-help"
        >
          <i class="ra ra-help text-[10px]"></i>
          Outdated format
          <span class="absolute left-0 top-full mt-2 w-60 p-3 rounded-xl bg-slate-900/95 border border-rose-500/30 text-[11px] font-normal text-slate-300 leading-relaxed shadow-2xl opacity-0 group-hover/legacy:opacity-100 transition-opacity pointer-events-none z-40">
            This session was created with an outdated adventure format. Unpredictable side effects may occur during gameplay.
          </span>
        </span>
      </div>

      <div class="flex gap-1.5 sm:gap-2 shrink-0">
        <div v-if="props.session.status_note" ref="noteRef" class="relative">
          <button
            @click.stop="isNoteOpen = !isNoteOpen"
            class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-black/45 backdrop-blur-md border border-amber-300/30 text-amber-300 hover:bg-black/70 transition-all flex items-center justify-center"
            title="Show note"
            aria-label="Show note"
          >
            <FileText class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          </button>
          <div
            v-if="isNoteOpen"
            class="absolute right-0 top-10 z-30 w-60 p-4 bg-[#0d1117]/95 border border-amber-200/15 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.8)] backdrop-blur-xl text-left"
          >
            <div class="font-fantasy text-xs font-bold tracking-wider text-amber-300 mb-2 pb-1.5 border-b border-white/10">Journal note</div>
            <p class="font-narrative text-sm text-slate-300 whitespace-pre-wrap leading-snug max-h-40 overflow-y-auto pr-1">{{ props.session.status_note }}</p>
          </div>
        </div>
        <SessionCardMenu v-model:open="isMenuOpen" @select="(action) => actionHandlers[action]()" />
      </div>
    </div>

    <!-- Wax seal for finished journeys -->
    <div
      v-if="statusView.seal"
      class="session-seal absolute z-10 right-3 sm:right-4 top-[38%] w-14 h-14 sm:w-[72px] sm:h-[72px] rounded-full flex flex-col items-center justify-center"
      :class="statusView.chipClass"
    >
      <i :class="['ra', statusView.icon]" class="text-lg sm:text-2xl"></i>
      <span class="font-fantasy font-bold text-[8px] sm:text-[10px] tracking-widest uppercase">{{ statusView.label }}</span>
    </div>

    <!-- Bottom: scene, title, stats, action -->
    <div class="tale-legible relative z-10 mt-auto p-2.5 sm:p-4 lg:p-5 flex flex-col gap-1.5 sm:gap-2.5">
      <div class="flex items-center gap-1.5 text-[10px] sm:text-[11px] font-bold min-w-0 text-slate-200">
        <i class="ra ra-compass shrink-0 tale-accent-text"></i>
        <span class="truncate">{{ props.session.current_scene_name || 'Exploring...' }}</span>
      </div>

      <h3 class="tale-title text-[13px] sm:text-lg lg:text-xl text-white leading-tight line-clamp-2 break-words">
        {{ props.session.adventure_title }}
      </h3>

      <div class="hidden sm:flex items-center gap-2 text-[10px] text-slate-400 min-w-0">
        <span :title="`${props.session.copied_from_id ? 'Cloned' : 'Started'} ${absoluteStart}`" class="truncate">Played {{ relativeLastPlayed }}</span>
        <span v-if="props.session.copied_from_id" class="px-1.5 py-px rounded border border-amber-400/30 bg-amber-500/15 text-amber-300 font-bold shrink-0">Clone</span>
        <span v-if="props.session.adventure_version" class="ml-auto px-1.5 py-px rounded border border-white/10 bg-black/30 font-mono shrink-0">v{{ props.session.adventure_version }}</span>
      </div>

      <div class="hidden sm:flex items-center gap-3 py-1 text-[11px] text-slate-300">
        <ProgressRing :value="props.session.progress || 0" :size="38" />
        <div class="flex flex-col gap-0.5 min-w-0">
          <span class="flex items-center gap-1.5" title="Quests completed">
            <i class="ra ra-scroll-unfurled text-slate-400"></i>{{ props.session.completed_quest_count || 0 }}/{{ props.session.quest_count || 0 }} quests
          </span>
          <span class="flex items-center gap-1.5" title="Awards earned">
            <i class="ra ra-trophy text-amber-300"></i>{{ props.session.earned_award_count || 0 }}/{{ props.session.award_count || 0 }} awards
          </span>
        </div>
        <span class="ml-auto flex items-center gap-1.5 text-slate-400 shrink-0" title="In-game time">
          <i class="ra ra-hourglass"></i>{{ playtime }}
        </span>
      </div>

      <button
        class="tale-action w-full py-2 sm:py-3 rounded-xl text-[10px] sm:text-xs font-bold tracking-wider uppercase flex items-center justify-center gap-2 transition-all"
        @click="emit('resume', props.session.game_id)"
      >
        <i v-if="statusView.seal" :class="['ra', statusView.icon]"></i>
        <Play v-else class="w-3.5 h-3.5 fill-current" />
        <span class="truncate">{{ statusView.action }}</span>
      </button>
    </div>
  </article>
</template>
