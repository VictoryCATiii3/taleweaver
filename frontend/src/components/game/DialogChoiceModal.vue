<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import type { PendingDialog } from '@/types'

/**
 * Choice dialog opened by an adventure script (tw.dialog.choose). It cannot be dismissed:
 * the story only continues once the player picks one of the options.
 */
const props = defineProps<{
  open: boolean
  dialog: PendingDialog | null
  busy?: boolean
  errorMessage?: string
}>()

const emit = defineEmits<{
  choose: [index: number]
}>()

const focusedIndex = ref(0)

watch(() => props.dialog?.id, () => {
  focusedIndex.value = 0
})

const choose = (index: number): void => {
  if (props.busy) return
  emit('choose', index)
}

const onKeyDown = (event: KeyboardEvent): void => {
  const options = props.dialog?.options || []
  if (!props.open || !options.length) return

  const handled = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Enter', ' ']
  const digit = Number.parseInt(event.key, 10)
  const isDigit = digit >= 1 && digit <= options.length
  if (!handled.includes(event.key) && !isDigit) return

  event.preventDefault()
  event.stopPropagation()

  if (isDigit) {
    choose(options[digit - 1].index)
    return
  }
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    focusedIndex.value = (focusedIndex.value + 1) % options.length
    return
  }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    focusedIndex.value = (focusedIndex.value - 1 + options.length) % options.length
    return
  }
  choose(options[focusedIndex.value].index)
}

onMounted(() => window.addEventListener('keydown', onKeyDown, { capture: true }))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, { capture: true }))
</script>

<template>
  <Teleport to="body">
    <Transition name="dlg-fade">
      <div
        v-if="open && dialog"
        class="fixed inset-0 z-[130] bg-black/75 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
      >
        <Transition name="dlg-scale" appear>
          <div class="w-full max-w-lg bg-slate-900 border border-amber-500/30 rounded-3xl shadow-2xl overflow-hidden">
            <!-- Header -->
            <div class="px-6 py-5 border-b border-slate-800/80 flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl border border-amber-500/40 bg-amber-500/10 flex items-center justify-center shrink-0">
                <i class="ra ra-speech-bubbles text-xl text-amber-400"></i>
              </div>
              <div class="min-w-0">
                <p class="text-[10px] font-black text-amber-400/80 uppercase tracking-widest">
                  {{ dialog.speaker ? 'Conversation' : 'Your choice' }}
                </p>
                <h3 class="text-base font-black text-white leading-tight truncate">
                  {{ dialog.speaker || 'What do you do?' }}
                </h3>
              </div>
            </div>

            <!-- Body -->
            <div class="p-6 space-y-5">
              <p v-if="dialog.prompt" class="text-sm text-slate-200 leading-relaxed whitespace-pre-line">
                {{ dialog.prompt }}
              </p>

              <div class="space-y-2">
                <button
                  v-for="(option, idx) in dialog.options"
                  :key="option.index"
                  :disabled="busy"
                  :class="[
                    'w-full flex items-center gap-3 px-4 py-3 rounded-2xl border text-left text-sm font-semibold transition-all duration-200 cursor-pointer disabled:cursor-wait',
                    focusedIndex === idx
                      ? 'bg-amber-500/15 border-amber-400/70 text-white ring-2 ring-amber-300/40 ring-offset-2 ring-offset-slate-900'
                      : 'bg-slate-800/40 border-slate-700/60 text-slate-300 hover:bg-slate-800/70 hover:border-slate-500 hover:text-white'
                  ]"
                  @click="choose(option.index)"
                  @mouseenter="focusedIndex = idx"
                >
                  <span class="w-6 h-6 rounded-full border border-slate-600/70 bg-slate-800 flex items-center justify-center shrink-0 font-mono text-[11px] text-amber-300">
                    {{ idx + 1 }}
                  </span>
                  <span class="flex-1">{{ option.label }}</span>
                  <i v-if="busy && focusedIndex === idx" class="ra ra-hourglass text-xs animate-spin opacity-60"></i>
                </button>
              </div>

              <p v-if="errorMessage" class="text-xs text-rose-400 text-center">{{ errorMessage }}</p>

              <p class="text-[10px] text-slate-600 text-center">
                Press
                <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">1</kbd>–<kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">{{ dialog.options.length }}</kbd>
                or use
                <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">↑ ↓</kbd>
                and
                <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 font-mono text-[9px]">Enter</kbd>
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dlg-fade-enter-active, .dlg-fade-leave-active {
  transition: opacity 0.2s ease;
}
.dlg-fade-enter-from, .dlg-fade-leave-to {
  opacity: 0;
}

.dlg-scale-enter-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.dlg-scale-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dlg-scale-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(8px);
}
.dlg-scale-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(4px);
}
</style>
