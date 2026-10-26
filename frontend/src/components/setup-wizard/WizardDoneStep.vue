<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle2, CircleDashed, MinusCircle } from 'lucide-vue-next'
import { settingsService } from '@/services/settingsService'
import { configState } from '@/store/config'
import { setupWizardState } from '@/store/setupWizard'
import { wizardStyles } from './wizardPresets'

defineProps<{ isStarting: boolean }>()

const emit = defineEmits<{
  (e: 'play'): void
  (e: 'open-admin'): void
}>()

type RowStatus = 'ok' | 'off' | 'missing'

const ICONS = { ok: CheckCircle2, off: MinusCircle, missing: CircleDashed }
const COLORS = { ok: 'text-emerald-400', off: 'text-slate-500', missing: 'text-amber-400' }

const rows = computed((): { label: string; status: RowStatus; detail: string }[] => {
  const keyCount = Object.keys(settingsService.configuredKeys.value).length
  const llm = settingsService.llmForm.value
  const t2i = settingsService.t2iForm.value
  const visualsStatus: RowStatus = configState.hasT2iConfig ? 'ok' : setupWizardState.visualsOptOut ? 'off' : 'missing'
  return [
    {
      label: 'API keys',
      status: keyCount > 0 ? 'ok' : 'off',
      detail: keyCount > 0 ? `${keyCount} configured` : 'None (fine for local models)',
    },
    {
      label: 'Intelligence',
      status: configState.hasLlmConfig ? 'ok' : 'missing',
      detail: configState.hasLlmConfig ? `${llm.complex_model} · ${llm.small_model}` : 'Required to play',
    },
    {
      label: 'Visuals',
      status: visualsStatus,
      detail: { ok: t2i.advanced_model, off: 'Text-only', missing: 'Not configured' }[visualsStatus],
    },
    {
      label: 'Voice',
      status: configState.isTtsEnabled ? 'ok' : 'off',
      detail: configState.isTtsEnabled ? settingsService.ttsForm.value.selected_model : 'Off',
    },
  ]
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h3 class="text-lg font-black text-white mb-2">
        {{ configState.hasLlmConfig ? 'You are ready to play' : 'Almost there' }}
      </h3>
      <p :class="wizardStyles.hint">
        Fine-tune token limits, play agent, image quality and more in the admin settings at any time.
      </p>
    </div>

    <ul class="space-y-2">
      <li
        v-for="row in rows"
        :key="row.label"
        class="flex items-center gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/5"
      >
        <component :is="ICONS[row.status]" class="w-5 h-5 shrink-0" :class="COLORS[row.status]" />
        <span class="w-28 text-sm font-bold text-white">{{ row.label }}</span>
        <span class="text-xs text-slate-400 truncate">{{ row.detail }}</span>
      </li>
    </ul>

    <div class="flex flex-wrap gap-3">
      <button
        type="button"
        class="px-5 py-3 rounded-xl bg-aether-primary text-slate-950 text-[10px] font-black uppercase tracking-[0.2em] hover:brightness-110 transition-all disabled:opacity-40"
        :disabled="!configState.hasLlmConfig || isStarting"
        @click="emit('play')"
      >
        {{ isStarting ? 'Starting…' : 'Play The Architect' }}
      </button>
      <button type="button" :class="wizardStyles.secondaryButton" @click="emit('open-admin')">
        Advanced settings
      </button>
    </div>
  </div>
</template>
