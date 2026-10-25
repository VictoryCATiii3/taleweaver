<script setup lang="ts">
import { computed } from 'vue'
import { SKINS, findSkin, type SkinId, type SkinPreference } from '@/skins/skinRegistry'

const skin = defineModel<SkinPreference>('skin', { required: true })

const props = defineProps<{
  /** Skin that "Auto" resolves to for this adventure. */
  autoSkin: SkinId
  /** Why Auto picked it, e.g. "chosen by the adventure author" or "matches the tone Mystery". */
  autoReason: string
}>()

const autoDefinition = computed(() => findSkin(props.autoSkin))
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-xs leading-relaxed text-slate-400">
      Choose how narration, dialogue and the story tabs look. Each skin changes colors, fonts and shapes but
      keeps the layout identical, so nothing moves around.
    </p>

    <div role="radiogroup" aria-label="Dialog skin" class="flex flex-col gap-2">
      <button
        type="button"
        role="radio"
        :aria-checked="skin === 'auto'"
        class="flex items-center gap-3 rounded-2xl border p-3 text-left transition-all cursor-pointer"
        :class="skin === 'auto' ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
        @click="skin = 'auto'"
      >
        <span class="flex h-10 w-14 shrink-0 overflow-hidden rounded-lg border border-white/10" aria-hidden="true">
          <span
            v-for="color in autoDefinition.swatch"
            :key="color"
            class="flex-1"
            :style="{ background: color }"
          ></span>
        </span>
        <span class="min-w-0 flex-1">
          <span class="block text-xs font-black uppercase tracking-widest text-slate-100">
            Auto · {{ autoDefinition.label }}
          </span>
          <span class="block text-xs leading-relaxed text-slate-400">Follows the adventure: {{ props.autoReason }}.</span>
        </span>
      </button>

      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button
          v-for="definition in SKINS"
          :key="definition.id"
          type="button"
          role="radio"
          :aria-checked="skin === definition.id"
          class="flex items-center gap-3 rounded-2xl border p-3 text-left transition-all cursor-pointer"
          :class="skin === definition.id ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
          @click="skin = definition.id"
        >
          <span class="flex h-10 w-10 shrink-0 overflow-hidden rounded-lg border border-white/10" aria-hidden="true">
            <span
              v-for="color in definition.swatch"
              :key="color"
              class="flex-1"
              :style="{ background: color }"
            ></span>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-xs font-black uppercase tracking-widest text-slate-100">{{ definition.label }}</span>
            <span class="block text-[11px] leading-snug text-slate-400">{{ definition.description }}</span>
          </span>
        </button>
      </div>
    </div>

    <p class="text-[11px] leading-relaxed text-slate-500">
      <span class="font-bold uppercase tracking-wider text-slate-400">How it works · </span>Auto uses the skin the
      adventure author picked; otherwise it matches the adventure's tone (for example Sci-Fi → Terminal,
      Mystery → Noir). Picking a skin here overrides that for every adventure on this device.
    </p>
  </div>
</template>
