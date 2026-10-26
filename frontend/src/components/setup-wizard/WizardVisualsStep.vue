<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ImageOff, RefreshCw } from 'lucide-vue-next'
import { settingsService } from '@/services/settingsService'
import { testService } from '@/services/testService'
import { configState } from '@/store/config'
import { setVisualsOptOut, setupWizardState } from '@/store/setupWizard'
import WizardTestResult from './WizardTestResult.vue'
import { IMAGE_PRESETS, needsKey, resolvePreset, wizardStyles, type SetupMode } from './wizardPresets'

const props = defineProps<{ mode: SetupMode }>()

const TEST_KEY = 'wizard-t2i'
const NO_IMAGES = 'none'

const t2iForm = settingsService.t2iForm
const constants = settingsService.availableConstants
const configuredKeys = computed(() => settingsService.configuredKeys.value)

const provider = ref(initialProvider())
const quickModel = ref('')
const sceneModel = ref('')
const ollamaUrl = ref(t2iForm.value.ollama_url || 'http://localhost:11434')
const stableDiffusionUrl = ref(t2iForm.value.stable_diffusion_url || 'http://127.0.0.1:7860')
const errorMessage = ref('')

const providers = computed(() => constants.value.image_providers)
const models = computed((): string[] => constants.value.predefined_image_models[provider.value] ?? [])
const isDisabled = computed((): boolean => provider.value === NO_IMAGES)
const providerNeedsKey = computed((): boolean => !isDisabled.value && needsKey(provider.value, configuredKeys.value))

function initialProvider(): string {
  if (configState.hasT2iConfig) {
    return t2iForm.value.advanced_model_provider
  }
  if (setupWizardState.visualsOptOut) {
    return NO_IMAGES
  }
  if (props.mode === 'local') {
    return 'stable_diffusion'
  }
  const withKey = settingsService.availableConstants.value.image_providers.find(
    (entry) => !needsKey(entry.id, settingsService.configuredKeys.value),
  )
  return withKey?.id ?? 'openai'
}

function applyPreset(): void {
  const keepCurrent = configState.hasT2iConfig && t2iForm.value.advanced_model_provider === provider.value
  if (keepCurrent) {
    quickModel.value = t2iForm.value.simple_model
    sceneModel.value = t2iForm.value.advanced_model
    return
  }
  const preset = resolvePreset(IMAGE_PRESETS, provider.value, models.value)
  quickModel.value = preset.fast
  sceneModel.value = preset.story
}

function runTest(): void {
  testService.testVision(TEST_KEY, sceneModel.value, provider.value, ollamaUrl.value, stableDiffusionUrl.value)
}

async function save(): Promise<boolean> {
  errorMessage.value = ''
  if (isDisabled.value) {
    await setVisualsOptOut(true)
    return true
  }
  if (!quickModel.value.trim() || !sceneModel.value.trim()) {
    errorMessage.value = 'Choose both models, pick "No images", or skip this page.'
    return false
  }
  const p = provider.value
  await settingsService.saveT2iSettings({
    ...t2iForm.value,
    simple_model: quickModel.value.trim(),
    simple_model_provider: p,
    advanced_model: sceneModel.value.trim(),
    advanced_model_provider: p,
    provider: p,
    ollama_url: ollamaUrl.value,
    stable_diffusion_url: stableDiffusionUrl.value,
  })
  if (settingsService.statusMessage.value?.type === 'error') {
    errorMessage.value = settingsService.statusMessage.value.text
    return false
  }
  await setVisualsOptOut(false)
  return true
}

watch(provider, () => {
  testService.clearResults(TEST_KEY)
  applyPreset()
})
applyPreset()

defineExpose({ save })
</script>

<template>
  <div class="space-y-5">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Visuals</h3>
      <p :class="wizardStyles.hint">
        Images bring covers, scenes and characters to life. TaleWeaver also works text-only.
      </p>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
      <button
        v-for="entry in providers"
        :key="entry.id"
        type="button"
        :class="[wizardStyles.option, provider === entry.id ? wizardStyles.optionActive : wizardStyles.optionIdle]"
        @click="provider = entry.id"
      >
        <p class="text-xs font-black text-white">{{ entry.name }}</p>
        <p v-if="needsKey(entry.id, configuredKeys)" class="text-[10px] text-amber-400 mt-1">No API key</p>
      </button>
      <button
        type="button"
        :class="[wizardStyles.option, isDisabled ? wizardStyles.optionActive : wizardStyles.optionIdle]"
        @click="provider = NO_IMAGES"
      >
        <p class="flex items-center gap-2 text-xs font-black text-white"><ImageOff class="w-4 h-4" /> No images</p>
      </button>
    </div>

    <p v-if="isDisabled" :class="wizardStyles.hint">
      Adventures will be text-only. You can enable images later in the admin settings.
    </p>

    <template v-else>
      <p v-if="providerNeedsKey" class="text-xs text-amber-400">
        No API key for this provider yet. Go back to the API keys page to add it.
      </p>

      <div v-if="provider === 'ollama'">
        <label :class="wizardStyles.label" for="wizard-t2i-ollama">Ollama URL</label>
        <input id="wizard-t2i-ollama" v-model="ollamaUrl" :class="wizardStyles.input" />
      </div>
      <div v-if="provider === 'stable_diffusion'" class="flex items-end gap-3">
        <div class="flex-1">
          <label :class="wizardStyles.label" for="wizard-sd-url">Stable Diffusion URL</label>
          <input id="wizard-sd-url" v-model="stableDiffusionUrl" :class="wizardStyles.input" />
        </div>
        <button
          type="button"
          :class="wizardStyles.secondaryButton"
          @click="settingsService.fetchStableDiffusionModels(stableDiffusionUrl)"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': settingsService.isLoadingStableDiffusionModels.value }" />
        </button>
      </div>

      <div class="grid sm:grid-cols-2 gap-4">
        <div>
          <label :class="wizardStyles.label" for="wizard-scene-model">Scene model (detailed)</label>
          <input id="wizard-scene-model" v-model="sceneModel" list="wizard-image-models" :class="wizardStyles.input" />
        </div>
        <div>
          <label :class="wizardStyles.label" for="wizard-quick-model">Asset model (quick)</label>
          <input id="wizard-quick-model" v-model="quickModel" list="wizard-image-models" :class="wizardStyles.input" />
        </div>
        <datalist id="wizard-image-models">
          <option v-for="model in models" :key="model" :value="model" />
        </datalist>
      </div>

      <div class="flex flex-wrap items-center gap-4">
        <button
          type="button"
          :class="wizardStyles.secondaryButton"
          :disabled="!sceneModel || providerNeedsKey"
          @click="runTest"
        >
          Generate test image
        </button>
        <WizardTestResult :test-key="TEST_KEY" />
      </div>
    </template>

    <p v-if="errorMessage" :class="wizardStyles.error">{{ errorMessage }}</p>
  </div>
</template>
