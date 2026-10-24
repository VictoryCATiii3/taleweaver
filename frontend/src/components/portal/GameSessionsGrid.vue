<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { GameSession } from '@/types'
import { Loader2 } from 'lucide-vue-next'
import GameSessionCard from './GameSessionCard.vue'
import { setAmbientAccent } from '@/store/portalAmbient'
import { lastPlayedMs } from '@/utils/relativeTime'

const props = defineProps<{
  sessions: GameSession[]
  hasMore?: boolean
  totalFilteredCount?: number
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'copy', gameId: string): void
  (e: 'switch-to-templates'): void
  (e: 'edit-note', gameId: string, currentNote: string): void
  (e: 'export', gameId: string): void
  (e: 'load-more'): void
}>()

const FINISHED_STATUSES = new Set(['completed', 'game_over', 'archived'])

/** Running journeys first, finished ones on their own shelf below; each shelf by last played. */
const shelves = computed(() =>
  [
    { key: 'ongoing', title: 'Ongoing Journeys', items: props.sessions.filter((s) => !FINISHED_STATUSES.has(s.status || '')) },
    { key: 'finished', title: 'Finished Tales', items: props.sessions.filter((s) => FINISHED_STATUSES.has(s.status || '')) },
  ]
    .map((shelf) => ({ ...shelf, items: [...shelf.items].sort((a, b) => lastPlayedMs(b) - lastPlayedMs(a)) }))
    .filter((shelf) => shelf.items.length > 0)
)

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
let scrollContainer: HTMLElement | null = null

function handleScroll() {
  if (!scrollContainer) return
  if (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 400) {
    emit('load-more')
  }
}

onMounted(() => {
  if (sentinelRef.value) {
    scrollContainer = sentinelRef.value.closest('.overflow-y-auto') as HTMLElement | null
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    }
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          emit('load-more')
        }
      },
      { root: scrollContainer, rootMargin: '400px' }
    )
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  setAmbientAccent(null)
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll)
  }
  if (observer) {
    observer.disconnect()
    observer = null
  }
})
</script>

<template>
  <div class="space-y-6">
    <div v-if="sessions.length === 0" class="tale-enter rounded-3xl border border-amber-200/10 bg-slate-900/40 p-8 sm:p-12 text-center flex flex-col items-center gap-4">
      <div class="forge-sigil w-16 h-16 sm:w-20 sm:h-20 rounded-full flex items-center justify-center text-3xl sm:text-4xl mb-1">
        <i class="ra ra-campfire"></i>
      </div>
      <h2 class="font-fantasy font-bold text-lg sm:text-xl text-white tracking-wide">The campfire is quiet</h2>
      <p class="font-narrative text-sm sm:text-base text-slate-400 max-w-md">
        No active sessions found matching your criteria. Discover new worlds in the Adventure Library and start your journey.
      </p>
      <button
        @click="$emit('switch-to-templates')"
        class="mt-2 px-5 sm:px-6 py-3 rounded-xl bg-aether-primary/10 border border-aether-primary/30 text-aether-primary font-bold hover:bg-aether-primary/20 transition-all uppercase tracking-widest text-xxs flex items-center gap-3"
      >
        <i class="ra ra-book text-sm"></i>
        Adventure Library
      </button>
    </div>
    
    <div v-else class="space-y-8 sm:space-y-10">
      <section v-for="shelf in shelves" :key="shelf.key" class="space-y-3" :aria-label="shelf.title">
        <h2 class="shelf-heading text-xs sm:text-sm uppercase">{{ shelf.title }}</h2>
        <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 sm:gap-4 xl:gap-5 pt-2">
          <div v-for="(entry, index) in shelf.items" :key="entry.game_id" class="tale-enter" :style="{ '--i': index }">
            <GameSessionCard
              :session="entry"
              @resume="(id) => $emit('resume', id)"
              @delete="(id, title) => $emit('delete', id, title)"
              @copy="(id) => $emit('copy', id)"
              @edit-note="(id, note) => $emit('edit-note', id, note)"
              @export="(id) => $emit('export', id)"
            />
          </div>
        </div>
      </section>

      <!-- Infinite Scroll Sentinel & Loader -->
      <div ref="sentinelRef" class="py-6 flex items-center justify-center">
        <div v-if="props.hasMore" class="flex items-center gap-2 text-xs text-slate-400 bg-black/40 px-4 py-2 rounded-xl border border-white/10">
          <Loader2 class="w-4 h-4 animate-spin text-aether-primary" />
          <span>Loading more sessions (showing {{ props.sessions.length }} of {{ props.totalFilteredCount }})...</span>
        </div>
        <div v-else-if="props.sessions.length > 8" class="text-xs text-slate-500">
          All {{ props.sessions.length }} sessions loaded
        </div>
      </div>
    </div>
  </div>
</template>
