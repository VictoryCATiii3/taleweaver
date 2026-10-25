<script setup lang="ts">
const model = defineModel<boolean>({ required: true })

const props = defineProps<{
  label: string
  disabled?: boolean
}>()
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="model"
    :aria-label="props.label"
    :disabled="props.disabled"
    class="relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
    :class="model ? 'bg-amber-500 border-amber-400' : 'bg-slate-800 border-slate-700'"
    @click="model = !model"
  >
    <span
      class="inline-block h-5 w-5 rounded-full shadow-md transition-transform duration-200"
      :class="model ? 'translate-x-6 bg-white' : 'translate-x-1 bg-slate-400'"
    ></span>
  </button>
</template>
