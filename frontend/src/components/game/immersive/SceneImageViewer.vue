<script setup lang="ts">
/**
 * SceneImageViewer — Shows the full scene artwork without any UI on top.
 * Fit-to-screen by default; clicking the image (or the 1:1 button) toggles the original size,
 * which can then be panned by scrolling. Escape or a click on the backdrop closes it.
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { X, Maximize, Minimize } from 'lucide-vue-next'

const props = defineProps<{
  imageUrl: string
  sceneName?: string | null
}>()

const emit = defineEmits<{
  close: []
}>()

const actualSize = ref(false)
const loaded = ref(false)

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[200] flex flex-col bg-black/95 backdrop-blur-sm animate-viewer-in"
      role="dialog"
      aria-modal="true"
      :aria-label="props.sceneName ? `Scene image: ${props.sceneName}` : 'Scene image'"
      @click.self="emit('close')"
    >
      <div class="flex items-center justify-between gap-3 px-4 py-3 shrink-0">
        <h2 class="min-w-0 truncate text-sm font-black uppercase tracking-widest text-white/90">
          {{ props.sceneName || 'Scene' }}
        </h2>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="flex h-10 items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 text-xs font-bold uppercase tracking-wider text-white/80 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            :aria-pressed="actualSize"
            :title="actualSize ? 'Fit to screen' : 'Show original size'"
            @click="actualSize = !actualSize"
          >
            <Minimize v-if="actualSize" class="h-4 w-4" />
            <Maximize v-else class="h-4 w-4" />
            <span class="hidden sm:inline">{{ actualSize ? 'Fit' : '1:1' }}</span>
          </button>
          <button
            type="button"
            class="flex h-10 w-10 items-center justify-center rounded-xl border border-white/15 bg-white/5 text-white/80 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            title="Close (Esc)"
            aria-label="Close scene image"
            @click="emit('close')"
          >
            <X class="h-5 w-5" />
          </button>
        </div>
      </div>

      <div
        class="relative min-h-0 flex-1"
        :class="actualSize ? 'overflow-auto' : 'flex items-center justify-center overflow-hidden p-3 sm:p-6'"
        @click.self="emit('close')"
      >
        <span
          v-if="!loaded"
          class="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 animate-spin rounded-full border-4 border-white/20 border-t-white/80"
          role="status"
          aria-label="Loading image"
        ></span>
        <img
          :src="props.imageUrl"
          :alt="props.sceneName || 'Scene image'"
          class="select-none transition-opacity duration-300"
          :class="[
            actualSize ? 'max-w-none cursor-zoom-out' : 'max-h-full max-w-full object-contain cursor-zoom-in rounded-lg shadow-2xl',
            loaded ? 'opacity-100' : 'opacity-0',
          ]"
          draggable="false"
          @load="loaded = true"
          @click="actualSize = !actualSize"
        />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.animate-viewer-in {
  animation: viewerIn 0.25s ease-out;
}

@keyframes viewerIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
