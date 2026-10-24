<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { MoreHorizontal, FileText, Download, Copy } from 'lucide-vue-next'

export type SessionCardAction = 'copy' | 'edit-note' | 'export' | 'delete'

const emit = defineEmits<{
  (e: 'select', action: SessionCardAction): void
}>()

const isOpen = defineModel<boolean>('open', { default: false })
const menuRef = ref<HTMLElement | null>(null)

const itemClass = 'w-full text-left px-4 py-2.5 text-xs font-bold tracking-wide flex items-center gap-2'
const neutralClass = `${itemClass} text-slate-300 hover:text-white hover:bg-white/5`

// A window listener instead of a fixed backdrop: the card's 3D transform would scope a fixed element to the card.
function handleClickOutside(event: MouseEvent): void {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    isOpen.value = false
  }
}

function select(action: SessionCardAction): void {
  emit('select', action)
  isOpen.value = false
}

onMounted(() => window.addEventListener('mousedown', handleClickOutside))
onUnmounted(() => window.removeEventListener('mousedown', handleClickOutside))
</script>

<template>
  <div ref="menuRef" class="relative">
    <button
      @click.stop="isOpen = !isOpen"
      class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-black/45 backdrop-blur-md border border-white/15 text-white hover:bg-black/70 hover:border-amber-300/40 transition-all flex items-center justify-center"
      title="Session actions"
      aria-label="Session actions"
      :aria-expanded="isOpen"
    >
      <MoreHorizontal class="w-3.5 h-3.5 sm:w-5 sm:h-5" />
    </button>

    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
      <div
        v-if="isOpen"
        class="absolute right-0 top-9 sm:top-10 z-30 w-48 bg-[#0d1117]/95 border border-amber-200/10 rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden backdrop-blur-xl py-1"
      >
        <button :class="neutralClass" @click="select('copy')">
          <Copy class="w-3.5 h-3.5" />
          Clone session
        </button>
        <button :class="neutralClass" @click="select('edit-note')">
          <FileText class="w-3.5 h-3.5 text-amber-400/80" />
          Edit note
        </button>
        <button :class="neutralClass" @click="select('export')">
          <Download class="w-3.5 h-3.5 text-emerald-400/80" />
          Export (.ads)
        </button>
        <div class="h-[1px] bg-white/5 mx-2 my-1"></div>
        <button :class="`${itemClass} text-red-400/70 hover:text-red-400 hover:bg-red-500/10`" @click="select('delete')">
          <i class="ra ra-skull text-xs"></i>
          Delete session
        </button>
      </div>
    </Transition>
  </div>
</template>
