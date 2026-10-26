<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Loader2, X } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { settingsService } from '@/services/settingsService'
import { authState } from '@/store/auth'
import { configState } from '@/store/config'
import type { SetupWizardState } from '@/composables/useApi'
import {
  closeSetupWizard,
  loadSetupWizard,
  missingSetupAreas,
  resetSetupWizard,
  setupWizardState,
} from '@/store/setupWizard'
import WizardWelcomeStep from './WizardWelcomeStep.vue'
import WizardKeysStep from './WizardKeysStep.vue'
import WizardLlmStep from './WizardLlmStep.vue'
import WizardVisualsStep from './WizardVisualsStep.vue'
import WizardSpeechStep from './WizardSpeechStep.vue'
import WizardDoneStep from './WizardDoneStep.vue'
import type { SetupMode, WizardStepHandle } from './wizardPresets'

const STEPS = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'keys', label: 'API Keys' },
  { id: 'llm', label: 'Intelligence' },
  { id: 'visuals', label: 'Visuals' },
  { id: 'tts', label: 'Voice' },
  { id: 'done', label: 'Done' },
] as const

const DEFAULT_ADVENTURE_TITLE = 'The Architect'

const router = useRouter()
const stepIndex = ref(0)
const mode = ref<SetupMode>('cloud')
const dontShowAgain = ref(false)
const isHydrating = ref(false)
const isSaving = ref(false)
const isStarting = ref(false)
const playError = ref('')
const stepRef = ref<WizardStepHandle | null>(null)

const currentStep = computed(() => STEPS[stepIndex.value].id)
const isFirst = computed((): boolean => stepIndex.value === 0)
const isLast = computed((): boolean => stepIndex.value === STEPS.length - 1)

/** Fresh installs start at Welcome; reopening jumps to the first unfinished area. */
function initialStep(): number {
  if (setupWizardState.state === 'pending') {
    return 0
  }
  const firstMissing = missingSetupAreas.value[0]
  if (firstMissing === 'llm') {
    return STEPS.findIndex((step) => step.id === 'keys')
  }
  if (firstMissing === 'visuals') {
    return STEPS.findIndex((step) => step.id === 'visuals')
  }
  return 0
}

async function hydrate(): Promise<void> {
  isHydrating.value = true
  dontShowAgain.value = false
  playError.value = ''
  stepIndex.value = initialStep()
  await settingsService.fetchSettings()
  mode.value = settingsService.llmForm.value.complex_model_provider === 'ollama' ? 'local' : 'cloud'
  isHydrating.value = false
}

async function next(): Promise<void> {
  isSaving.value = true
  const saved = (await stepRef.value?.save?.()) ?? true
  isSaving.value = false
  if (saved) {
    stepIndex.value += 1
  }
}

function skipStep(): void {
  stepIndex.value += 1
}

function back(): void {
  stepIndex.value -= 1
}

async function close(reason: SetupWizardState): Promise<void> {
  await closeSetupWizard(dontShowAgain.value ? 'dismissed' : reason)
}

async function openAdmin(): Promise<void> {
  await close('completed')
  await router.push('/admin')
}

async function playDefaultAdventure(): Promise<void> {
  isStarting.value = true
  playError.value = ''
  try {
    const templates = await api.listAdventureTemplates()
    const template = templates.find((entry) => entry.title === DEFAULT_ADVENTURE_TITLE && entry.is_ready)
    if (!template) {
      playError.value = `"${DEFAULT_ADVENTURE_TITLE}" was not found in your library.`
      return
    }
    const session = await api.startSessionForTemplate(template.template_id)
    await close('completed')
    await router.push({ name: 'game', params: { id: session.game_id }, query: { title: template.title, is_new: 'true' } })
  } catch (error) {
    console.error('[SetupWizard] Starting the default adventure failed:', error)
    playError.value = 'The adventure could not be started.'
  } finally {
    isStarting.value = false
  }
}

watch(
  () => [authState.user?.id, configState.isLoaded] as const,
  ([userId, isLoaded]) => {
    if (!userId) {
      resetSetupWizard()
      return
    }
    if (isLoaded) {
      loadSetupWizard()
    }
  },
  { immediate: true },
)

watch(
  () => setupWizardState.isOpen,
  (isOpen) => {
    if (isOpen) {
      hydrate()
    }
  },
)
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="setupWizardState.isOpen"
      class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="setup-wizard-title"
    >
      <div class="relative w-full max-w-2xl max-h-[92vh] flex flex-col bg-[#0d1117] border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-aether-primary to-transparent"></div>

        <!-- Header + step indicator -->
        <div class="px-8 pt-7 pb-5 border-b border-white/5">
          <div class="flex items-center justify-between mb-5">
            <div>
              <h2 id="setup-wizard-title" class="text-xl font-black text-white uppercase tracking-tighter leading-none mb-1">
                Setup Assistant
              </h2>
              <p class="text-aether-primary/60 text-[10px] font-bold uppercase tracking-[0.2em]">
                Step {{ stepIndex + 1 }} of {{ STEPS.length }}
              </p>
            </div>
            <button
              type="button"
              class="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/5 transition-all"
              title="Close (skip for now)"
              aria-label="Close setup assistant"
              @click="close(isLast ? 'completed' : 'skipped')"
            >
              <X class="w-6 h-6" />
            </button>
          </div>
          <ol class="flex gap-1.5">
            <li v-for="(step, index) in STEPS" :key="step.id" class="flex-1">
              <div
                class="h-1 rounded-full transition-colors"
                :class="index <= stepIndex ? 'bg-aether-primary' : 'bg-white/10'"
              ></div>
              <span
                class="hidden sm:block mt-2 text-[9px] font-black uppercase tracking-widest"
                :class="index === stepIndex ? 'text-white' : 'text-slate-600'"
              >
                {{ step.label }}
              </span>
            </li>
          </ol>
        </div>

        <!-- Page -->
        <div class="flex-1 overflow-y-auto px-8 py-6">
          <div v-if="isHydrating" class="flex items-center gap-3 text-sm text-slate-400 py-12 justify-center">
            <Loader2 class="w-5 h-5 animate-spin" /> Loading current settings…
          </div>
          <template v-else>
            <WizardWelcomeStep v-if="currentStep === 'welcome'" v-model="mode" />
            <WizardKeysStep v-else-if="currentStep === 'keys'" ref="stepRef" :mode="mode" />
            <WizardLlmStep v-else-if="currentStep === 'llm'" ref="stepRef" :mode="mode" />
            <WizardVisualsStep v-else-if="currentStep === 'visuals'" ref="stepRef" :mode="mode" />
            <WizardSpeechStep v-else-if="currentStep === 'tts'" ref="stepRef" />
            <WizardDoneStep
              v-else
              :is-starting="isStarting"
              @play="playDefaultAdventure"
              @open-admin="openAdmin"
            />
            <p v-if="playError && currentStep === 'done'" class="mt-4 text-xs font-bold text-red-400">{{ playError }}</p>
          </template>
        </div>

        <!-- Footer -->
        <div class="px-8 py-5 border-t border-white/5 flex flex-col-reverse sm:flex-row sm:items-center justify-between gap-4">
          <label class="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
            <input v-model="dontShowAgain" type="checkbox" class="w-4 h-4 accent-emerald-400" />
            Don't show the setup assistant again
          </label>
          <div class="flex items-center gap-2 justify-end">
            <button
              v-if="!isFirst"
              type="button"
              class="px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-white transition-all"
              :disabled="isSaving"
              @click="back"
            >
              Back
            </button>
            <button
              v-if="!isFirst && !isLast"
              type="button"
              class="px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-white transition-all"
              :disabled="isSaving"
              @click="skipStep"
            >
              Skip step
            </button>
            <button
              v-if="!isLast"
              type="button"
              class="px-6 py-2.5 rounded-xl bg-aether-primary text-slate-950 text-[10px] font-black uppercase tracking-[0.2em] hover:brightness-110 transition-all disabled:opacity-50"
              :disabled="isSaving || isHydrating"
              @click="next"
            >
              {{ isSaving ? 'Saving…' : isFirst ? "Let's go" : 'Save & continue' }}
            </button>
            <button
              v-else
              type="button"
              class="px-6 py-2.5 rounded-xl bg-white/10 text-white text-[10px] font-black uppercase tracking-[0.2em] hover:bg-white/15 transition-all"
              @click="close('completed')"
            >
              Finish
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
