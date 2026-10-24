<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** Completion in percent (0-100). */
    value: number
    size?: number
    stroke?: number
  }>(),
  { size: 40, stroke: 3 }
)

const radius = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const offset = computed(() => {
  const clamped = Math.min(100, Math.max(0, props.value || 0))
  return circumference.value * (1 - clamped / 100)
})
</script>

<template>
  <div class="relative inline-flex items-center justify-center shrink-0" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg class="progress-ring -rotate-90" :width="size" :height="size" aria-hidden="true">
      <circle :cx="size / 2" :cy="size / 2" :r="radius" fill="rgb(2 6 23 / 0.6)" stroke="rgb(255 255 255 / 0.12)" :stroke-width="stroke" />
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="rgb(var(--accent-rgb, 78 222 163))"
        stroke-linecap="round"
        :stroke-width="stroke"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
      />
    </svg>
    <span class="absolute text-[10px] font-bold text-white">{{ Math.round(value || 0) }}%</span>
  </div>
</template>
