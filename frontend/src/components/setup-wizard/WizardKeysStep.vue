<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckCircle2, Server } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { settingsService } from '@/services/settingsService'
import { refreshConfig } from '@/store/config'
import { KEY_PROVIDERS, wizardStyles, type SetupMode } from './wizardPresets'

const props = defineProps<{ mode: SetupMode }>()

const drafts = ref<Record<string, string>>({})
const errorMessage = ref('')
const configuredKeys = computed(() => settingsService.configuredKeys.value)

function keyStatus(provider: string): 'env' | 'saved' | 'missing' {
  const key = configuredKeys.value[provider]
  if (!key) {
    return 'missing'
  }
  return key.is_env ? 'env' : 'saved'
}

async function save(): Promise<boolean> {
  errorMessage.value = ''
  const entries = Object.entries(drafts.value).filter(([, value]) => value.trim())
  const failed: string[] = []
  for (const [provider, value] of entries) {
    try {
      await api.saveApiKey(provider, value)
    } catch (error) {
      console.error(`[SetupWizard] Saving ${provider} key failed:`, error)
      failed.push(provider)
    }
  }
  if (entries.length > 0) {
    await settingsService.fetchSettings()
    await refreshConfig()
  }
  drafts.value = Object.fromEntries(failed.map((provider) => [provider, drafts.value[provider]]))
  if (failed.length > 0) {
    errorMessage.value = `Could not save: ${failed.join(', ')}.`
    return false
  }
  return true
}

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">API keys</h3>
      <p :class="wizardStyles.hint">
        <template v-if="props.mode === 'local'">
          Running locally needs no keys. Add one only if you want to mix in a cloud provider, e.g.
          for images or voice.
        </template>
        <template v-else>
          Add a key for at least one text provider. Keys are stored encrypted on the server and are
          never shown again.
        </template>
      </p>
    </div>

    <div class="space-y-2 max-h-[46vh] overflow-y-auto pr-1">
      <div
        v-for="provider in KEY_PROVIDERS"
        :key="provider.id"
        class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/5"
      >
        <div class="sm:w-44 shrink-0">
          <p class="text-sm font-bold text-white">{{ provider.name }}</p>
          <p class="text-[10px] uppercase tracking-widest text-slate-500">{{ provider.uses }}</p>
        </div>
        <div v-if="keyStatus(provider.id) === 'env'" class="flex items-center gap-2 text-xs text-slate-400">
          <Server class="w-4 h-4 text-sky-400" /> Provided by the server environment
        </div>
        <div v-else class="flex-1 flex items-center gap-3">
          <input
            v-model="drafts[provider.id]"
            type="password"
            autocomplete="off"
            :placeholder="keyStatus(provider.id) === 'saved' ? 'Saved — enter a new key to replace it' : 'Paste API key'"
            :class="wizardStyles.input"
          />
          <CheckCircle2 v-if="keyStatus(provider.id) === 'saved'" class="w-5 h-5 text-emerald-400 shrink-0" />
        </div>
      </div>
    </div>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
