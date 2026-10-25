<script setup lang="ts">
import { BABLE_FISH_LANGUAGES } from './bableFishLanguages'

const language = defineModel<string>('language', { required: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-start gap-3 rounded-2xl border border-cyan-500/20 bg-cyan-500/[0.06] p-4">
      <i class="ra ra-fish mt-0.5 shrink-0 text-lg text-cyan-400"></i>
      <div class="space-y-1.5">
        <h4 class="text-xs font-black uppercase tracking-widest text-cyan-200">Bable Fish</h4>
        <p class="text-xs italic leading-relaxed text-slate-400">
          "Small, yellow, and probably the oddest thing in the Universe."
        </p>
        <p class="text-xs leading-relaxed text-slate-300">
          Translates all narration and dialogue into your chosen language while it is generated. Choose
          <span class="font-bold text-white">Default</span> to play in the adventure's original language.
        </p>
      </div>
    </div>

    <div role="radiogroup" aria-label="Bable Fish language" class="grid grid-cols-2 gap-2 sm:grid-cols-3">
      <button
        v-for="lang in BABLE_FISH_LANGUAGES"
        :key="lang.code"
        type="button"
        role="radio"
        :aria-checked="language === lang.code"
        class="flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-all cursor-pointer"
        :class="
          language === lang.code
            ? 'border-cyan-400/60 bg-cyan-500/15 text-white shadow-[0_0_14px_-4px_rgba(34,211,238,0.5)]'
            : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-white'
        "
        @click="language = lang.code"
      >
        <i :class="['ra shrink-0 text-sm', lang.icon, language === lang.code ? 'text-cyan-300' : 'text-slate-500']"></i>
        <span class="min-w-0 flex-1 truncate text-xs font-bold tracking-wide">{{ lang.name }}</span>
        <span v-if="lang.code" class="font-mono text-[10px] text-slate-500">{{ lang.short }}</span>
      </button>
    </div>

    <p class="text-[11px] leading-relaxed text-slate-500">
      <span class="font-bold uppercase tracking-wider text-slate-400">How it works · </span>The translation also
      drives the language of speech output. The compressed chronicle summary always stays in English. Until you pick
      a language here, the default language from your profile is used.
    </p>
  </div>
</template>
