<script setup lang="ts">
import type { GenreAccent } from '@/composables/useGenreAccent'

/**
 * Artwork layer for portrait tale cards. Covers are generated at 3:2, so instead of cropping them
 * into the 2:3 card, the full cover sits at the top and a blurred copy fills the space below it.
 */
defineProps<{
  imageUrl: string | null
  accent: GenreAccent
  /** Desaturates the art, e.g. for defeated sessions. */
  muted?: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 overflow-hidden rounded-2xl bg-slate-950" :class="muted ? 'grayscale-[85%] brightness-75' : ''">
    <template v-if="imageUrl">
      <img :src="imageUrl" alt="" aria-hidden="true" class="absolute inset-0 w-full h-full object-cover scale-125 blur-2xl brightness-[0.45] saturate-150" />
      <img
        :src="imageUrl"
        alt=""
        loading="lazy"
        class="tale-card__cover relative w-full aspect-[3/2] object-cover transition-transform duration-[1200ms] ease-out group-hover:scale-105"
      />
    </template>
    <div
      v-else
      class="w-full h-full flex items-start justify-center pt-[18%]"
      :style="{ background: `radial-gradient(circle at 50% 25%, rgb(${accent.rgb} / 0.18), transparent 65%)` }"
    >
      <i :class="['ra', accent.icon]" class="text-5xl sm:text-7xl opacity-40" :style="{ color: `rgb(${accent.rgb})` }"></i>
    </div>
    <div class="tale-card__shade absolute inset-0"></div>
    <div class="tale-card__glare absolute inset-0"></div>
    <div class="tale-embers absolute inset-0" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>
    <div class="tale-card__frame absolute inset-0"><div class="tale-card__frame-bl"></div></div>
  </div>
</template>
