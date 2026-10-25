<script setup lang="ts">
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

/** Inline on_interact trigger (script + text) shared by objects and NPCs. */
defineProps<{
  entityLabel: string
}>()

const script = defineModel<string>('script', { default: '' })
const text = defineModel<string>('text', { default: '' })
</script>

<template>
  <div class="space-y-4 border border-white/5 bg-black/20 p-4 rounded-xl">
    <ScriptEditor
      v-model="script"
      label="On Interact Script"
      :help-text="`Executed whenever the player interacts with this ${entityLabel} (inspect, use, push, talk, tamper). Works for fixed objects too. For behaviour limited to one chapter, use a sequence script instead.`"
      context="on_interact"
      min-height="120px"
    />
    <div class="space-y-2">
      <div class="flex items-center gap-2">
        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">On Interact Text</label>
        <div class="group relative flex items-center">
          <i class="ra ra-help text-slate-500 hover:text-white cursor-help transition-colors text-xs"></i>
          <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50">
            A text shown to the player every time they interact with this {{ entityLabel }}.
          </div>
        </div>
      </div>
      <textarea v-model="text" rows="3" class="w-full bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-xs text-slate-300 focus:border-cyan-500 outline-none transition-all resize-y"></textarea>
    </div>
  </div>
</template>
