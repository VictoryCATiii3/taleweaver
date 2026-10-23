<script setup lang="ts">
import GeneratorLightbox from '@/components/game/generator/GeneratorLightbox.vue'

defineProps<{
  imageUrl: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <!-- Teleported with its own stacking layer so it renders above the z-[200] editor modals -->
  <Teleport to="body">
    <div v-if="imageUrl" class="relative z-[300]">
      <GeneratorLightbox :image-url="imageUrl" @close="emit('close')" />
    </div>
  </Teleport>
</template>
