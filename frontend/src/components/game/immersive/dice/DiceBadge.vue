<script setup lang="ts">
/**
 * DiceBadge — Skinned die graphic showing a rolled value. A d6 shows pips; other dice show
 * their silhouette (d4 triangle, d8 diamond, d10/d12 pentagon, d20+ hexagon) with the number.
 * Tumbles in when it appears; natural max glows, natural 1 turns red.
 */
import { computed } from 'vue'

const props = defineProps<{
  value: number
  sides: number
  isCrit?: boolean
  isFumble?: boolean
  /** Skip the tumble animation (e.g. in the System log). */
  still?: boolean
}>()

// Pip positions on a 0..100 grid for each d6 face.
const PIP_LAYOUTS: Record<number, [number, number][]> = {
  1: [[50, 50]],
  2: [[28, 28], [72, 72]],
  3: [[28, 28], [50, 50], [72, 72]],
  4: [[28, 28], [72, 28], [28, 72], [72, 72]],
  5: [[28, 28], [72, 28], [50, 50], [28, 72], [72, 72]],
  6: [[28, 26], [72, 26], [28, 50], [72, 50], [28, 74], [72, 74]],
}

const SHAPES: { maxSides: number; points: string }[] = [
  { maxSides: 4, points: '50,8 94,88 6,88' },
  { maxSides: 8, points: '50,4 94,50 50,96 6,50' },
  { maxSides: 12, points: '50,5 95,38 78,93 22,93 5,38' },
  { maxSides: Infinity, points: '50,4 92,27 92,73 50,96 8,73 8,27' },
]

const isD6 = computed(() => props.sides === 6)
const pips = computed(() => PIP_LAYOUTS[props.value] ?? [])
const shapePoints = computed(() => SHAPES.find((shape) => props.sides <= shape.maxSides)?.points ?? '')
const numberSize = computed(() => (props.value >= 10 ? 34 : 42))
const label = computed(() => {
  const suffix = props.isCrit ? ', critical' : props.isFumble ? ', fumble' : ''
  return `d${props.sides} rolled ${props.value}${suffix}`
})
</script>

<template>
  <span
    class="tw-die"
    :class="{ 'tw-die--crit': props.isCrit, 'tw-die--fumble': props.isFumble && !props.isCrit, 'tw-die--still': props.still }"
    role="img"
    :aria-label="label"
  >
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <template v-if="isD6">
        <rect class="tw-die-face" x="6" y="6" width="88" height="88" rx="18" />
        <rect class="tw-die-shine" x="14" y="12" width="72" height="20" rx="10" />
        <circle v-for="([cx, cy], idx) in pips" :key="idx" class="tw-die-pip" :cx="cx" :cy="cy" r="8.5" />
      </template>
      <template v-else>
        <polygon class="tw-die-face" :points="shapePoints" stroke-linejoin="round" />
        <text class="tw-die-number" x="50" y="54" text-anchor="middle" dominant-baseline="middle" :font-size="numberSize">
          {{ props.value }}
        </text>
      </template>
    </svg>
    <span class="tw-die-sides">d{{ props.sides }}</span>
  </span>
</template>
