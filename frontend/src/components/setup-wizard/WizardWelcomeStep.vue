<script setup lang="ts">
import { Cloud, HardDrive } from 'lucide-vue-next'
import { wizardStyles, type SetupMode } from './wizardPresets'

const mode = defineModel<SetupMode>({ required: true })

const options = [
  {
    id: 'cloud' as SetupMode,
    icon: Cloud,
    title: 'Cloud providers',
    text: 'Use API keys for OpenAI, Anthropic, Google and others. Best quality, quickest setup.',
  },
  {
    id: 'local' as SetupMode,
    icon: HardDrive,
    title: 'Run locally',
    text: 'Use Ollama for text and Stable Diffusion for images on your own hardware. No API keys needed.',
  },
]
</script>

<template>
  <div class="space-y-6">
    <div>
      <h3 class="text-lg font-black text-white mb-2">Welcome to TaleWeaver</h3>
      <p :class="wizardStyles.hint">
        A few settings are needed before the Game Master can tell stories: an AI model for text,
        optionally an image generator and a voice. This takes about two minutes. You can skip any
        page and change everything later in the admin settings.
      </p>
    </div>

    <div>
      <span :class="wizardStyles.label">How do you want to run TaleWeaver?</span>
      <div class="grid sm:grid-cols-2 gap-3">
        <button
          v-for="option in options"
          :key="option.id"
          type="button"
          :class="[wizardStyles.option, mode === option.id ? wizardStyles.optionActive : wizardStyles.optionIdle]"
          @click="mode = option.id"
        >
          <component :is="option.icon" class="w-5 h-5 text-aether-primary mb-3" />
          <p class="text-sm font-black text-white mb-1">{{ option.title }}</p>
          <p :class="wizardStyles.hint">{{ option.text }}</p>
        </button>
      </div>
    </div>

    <p class="text-xs text-slate-400">
      Your first adventure, <span class="font-bold text-white">The Architect</span>, is already in
      your library and ready to play once the setup is done.
    </p>
  </div>
</template>
