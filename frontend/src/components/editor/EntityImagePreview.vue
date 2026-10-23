<script setup lang="ts">
import { ref, watch } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import GeneratorLightbox from '@/components/game/generator/GeneratorLightbox.vue'

const props = defineProps<{
  imageUrl: string | null
  label?: string
}>()

const enlargedUrl = ref<string | null>(null)

watch(() => props.imageUrl, () => {
  enlargedUrl.value = null
})

function openLightbox() {
  if (!props.imageUrl) return
  enlargedUrl.value = props.imageUrl
}
</script>

<template>
  <button
    v-if="imageUrl"
    type="button"
    class="group relative w-14 h-14 shrink-0 rounded-2xl overflow-hidden border border-white/10 bg-black/40 hover:border-emerald-500/60 transition-colors"
    :title="`View ${label || 'image'} in full size`"
    @click="openLightbox"
  >
    <img :src="imageUrl" :alt="label || 'Entity image'" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
    <span class="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity">
      <Maximize2 class="w-4 h-4 text-white" />
    </span>
  </button>

  <!-- Teleported with its own stacking layer so it renders above the z-[200] editor modal -->
  <Teleport to="body">
    <div v-if="enlargedUrl" class="relative z-[300]">
      <GeneratorLightbox :image-url="enlargedUrl" @close="enlargedUrl = null" />
    </div>
  </Teleport>
</template>
