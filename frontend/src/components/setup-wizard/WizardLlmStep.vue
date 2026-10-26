<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { settingsService } from '@/services/settingsService'
import { testService } from '@/services/testService'
import { configState } from '@/store/config'
import WizardTestResult from './WizardTestResult.vue'
import { LLM_PRESETS, needsKey, resolvePreset, wizardStyles, type SetupMode } from './wizardPresets'

const props = defineProps<{ mode: SetupMode }>()

const TEST_KEY = 'wizard-llm'

const llmForm = settingsService.llmForm
const constants = settingsService.availableConstants
const configuredKeys = computed(() => settingsService.configuredKeys.value)

const provider = ref(initialProvider())
const fastModel = ref('')
const storyModel = ref('')
const ollamaUrl = ref(llmForm.value.ollama_url || 'http://localhost:11434')
const errorMessage = ref('')

const providers = computed(() => constants.value.llm_providers)
const models = computed((): string[] => constants.value.predefined_llm_models[provider.value] ?? [])
const providerNeedsKey = computed((): boolean => needsKey(provider.value, configuredKeys.value))

function initialProvider(): string {
  if (configState.hasLlmConfig) {
    return llmForm.value.complex_model_provider
  }
  if (props.mode === 'local') {
    return 'ollama'
  }
  const withKey = settingsService.availableConstants.value.llm_providers.find(
    (entry) => !needsKey(entry.id, settingsService.configuredKeys.value),
  )
  return withKey?.id ?? 'openai'
}

function applyPreset(): void {
  const keepCurrent = configState.hasLlmConfig && llmForm.value.complex_model_provider === provider.value
  if (keepCurrent) {
    fastModel.value = llmForm.value.small_model
    storyModel.value = llmForm.value.complex_model
    return
  }
  const preset = resolvePreset(LLM_PRESETS, provider.value, models.value)
  fastModel.value = preset.fast
  storyModel.value = preset.story
}

async function refreshOllamaModels(): Promise<void> {
  await settingsService.fetchOllamaModels(ollamaUrl.value)
  if (!models.value.includes(storyModel.value)) {
    applyPreset()
  }
}

function runTest(): void {
  testService.testLlm(TEST_KEY, storyModel.value, provider.value, ollamaUrl.value)
}

/** Fills empty secondary roles with the fast model; existing custom choices are left alone. */
function secondaryRoles(): Record<string, string> {
  const roles: Record<string, string> = {}
  if (!llmForm.value.play_agent_model) {
    roles.play_agent_model = fastModel.value.trim()
    roles.play_agent_model_provider = provider.value
  }
  if (!llmForm.value.compression_model) {
    roles.compression_model = fastModel.value.trim()
    roles.compression_model_provider = provider.value
  }
  return roles
}

async function save(): Promise<boolean> {
  errorMessage.value = ''
  if (!fastModel.value.trim() || !storyModel.value.trim()) {
    errorMessage.value = 'Choose both models, or skip this page.'
    return false
  }
  const p = provider.value
  await settingsService.saveLlmSettings({
    ...llmForm.value,
    small_model: fastModel.value.trim(),
    small_model_provider: p,
    complex_model: storyModel.value.trim(),
    complex_model_provider: p,
    generator_model: storyModel.value.trim(),
    generator_model_provider: p,
    ...secondaryRoles(),
    preferred_provider: p,
    ollama_url: ollamaUrl.value,
  })
  if (settingsService.statusMessage.value?.type === 'error') {
    errorMessage.value = settingsService.statusMessage.value.text
    return false
  }
  return true
}

watch(provider, () => {
  testService.clearResults(TEST_KEY)
  applyPreset()
})
applyPreset()
if (provider.value === 'ollama') {
  refreshOllamaModels()
}

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Intelligence</h3>
      <p :class="wizardStyles.hint">
        The Game Master uses a strong <span class="text-slate-300">story model</span> for narration
        and world building, and a cheaper <span class="text-slate-300">fast model</span> for quick
        checks. This is required to play.
      </p>
    </div>

    <div>
      <label :class="wizardStyles.label" for="wizard-llm-provider">Provider</label>
      <select id="wizard-llm-provider" v-model="provider" :class="wizardStyles.input">
        <option v-for="entry in providers" :key="entry.id" :value="entry.id" class="bg-slate-900">
          {{ entry.name }}{{ needsKey(entry.id, configuredKeys) ? ' — no API key' : '' }}
        </option>
      </select>
      <p v-if="providerNeedsKey" class="mt-2 text-xs text-amber-400">
        No API key for this provider yet. Go back one page to add it.
      </p>
    </div>

    <div v-if="provider === 'ollama'" class="flex items-end gap-3">
      <div class="flex-1">
        <label :class="wizardStyles.label" for="wizard-ollama-url">Ollama URL</label>
        <input id="wizard-ollama-url" v-model="ollamaUrl" :class="wizardStyles.input" />
      </div>
      <button type="button" :class="wizardStyles.secondaryButton" @click="refreshOllamaModels">
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': settingsService.isLoadingOllamaModels.value }" />
      </button>
    </div>

    <div class="grid sm:grid-cols-2 gap-4">
      <div>
        <label :class="wizardStyles.label" for="wizard-story-model">Story model</label>
        <input id="wizard-story-model" v-model="storyModel" list="wizard-llm-models" :class="wizardStyles.input" />
      </div>
      <div>
        <label :class="wizardStyles.label" for="wizard-fast-model">Fast model</label>
        <input id="wizard-fast-model" v-model="fastModel" list="wizard-llm-models" :class="wizardStyles.input" />
      </div>
      <datalist id="wizard-llm-models">
        <option v-for="model in models" :key="model" :value="model" />
      </datalist>
    </div>

    <div class="flex flex-wrap items-center gap-4">
      <button
        type="button"
        :class="wizardStyles.secondaryButton"
        :disabled="!storyModel || providerNeedsKey"
        @click="runTest"
      >
        Test connection
      </button>
      <WizardTestResult :test-key="TEST_KEY" />
    </div>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
