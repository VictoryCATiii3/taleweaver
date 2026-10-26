<script setup lang="ts">
import { Wand2 } from 'lucide-vue-next'
import { missingSetupAreas, openSetupWizard, showSetupWizardButton } from '@/store/setupWizard'
</script>

<template>
  <button
    v-if="showSetupWizardButton"
    type="button"
    class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 hover:text-amber-300 transition-all"
    title="Open the setup assistant"
    @click="openSetupWizard"
  >
    <Wand2 class="w-4 h-4" />
    <span class="hidden sm:inline text-[10px] font-black uppercase tracking-[0.2em]">Finish setup</span>
    <span class="min-w-5 h-5 px-1 rounded-full bg-amber-500 text-slate-950 text-[10px] font-black flex items-center justify-center">
      {{ missingSetupAreas.length }}
    </span>
  </button>
</template>
