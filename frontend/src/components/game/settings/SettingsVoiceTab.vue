<script setup lang="ts">
import { VolumeX } from 'lucide-vue-next'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'

const autoSpeech = defineModel<boolean>('autoSpeech', { required: true })
const autoSpeakNarration = defineModel<boolean>('autoSpeakNarration', { required: true })
const autoSpeakDialogues = defineModel<boolean>('autoSpeakDialogues', { required: true })

const props = defineProps<{
  ttsAvailable: boolean
}>()
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-xs leading-relaxed text-slate-400">
      Let the Game Master and the characters speak. New story passages are converted to speech as they arrive,
      using the voices configured for the adventure.
    </p>

    <div
      v-if="!props.ttsAvailable"
      class="flex items-start gap-3 rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4 text-xs leading-relaxed text-slate-400"
    >
      <VolumeX class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
      <span>
        Speech output is not available. An administrator has to enable and configure a text-to-speech provider in
        the system settings first.
      </span>
    </div>

    <template v-else>
      <SettingCard
        title="Auto-Speak"
        badge="Audio"
        badge-tone="blue"
        description="Master switch: automatically read new narration and dialogue aloud."
        hint="Only passages that arrive after you enable this are spoken, so your existing log is not replayed. Some browsers block audio until you have interacted with the page once."
      >
        <template #control>
          <SettingToggle v-model="autoSpeech" label="Auto-Speak" />
        </template>
      </SettingCard>

      <SettingCard
        title="Game Master Voice"
        description="Speak the narrator's descriptions of scenes, events and outcomes."
        :disabled="!autoSpeech"
      >
        <template #control>
          <SettingToggle v-model="autoSpeakNarration" label="Auto-speak Game Master" :disabled="!autoSpeech" />
        </template>
      </SettingCard>

      <SettingCard
        title="Character Voices"
        description="Speak dialogue bubbles of NPCs and your own character, each with their assigned voice."
        hint="Disable this if you prefer to read dialogue yourself while keeping the narration audible. Speech pauses automatically during combat."
        :disabled="!autoSpeech"
      >
        <template #control>
          <SettingToggle v-model="autoSpeakDialogues" label="Auto-speak characters" :disabled="!autoSpeech" />
        </template>
      </SettingCard>
    </template>
  </div>
</template>
