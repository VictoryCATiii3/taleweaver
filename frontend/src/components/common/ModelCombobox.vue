<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown, RefreshCw } from 'lucide-vue-next'
import type { ModelKind } from '@/composables/useApi'
import { getProviderModelsEntry, loadProviderModels, providerModelsKey } from '@/store/providerModels'

/**
 * Model picker backed by live provider discovery. Typing filters the list; any value
 * can still be entered manually (new or private models).
 */
const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{
  provider: string
  kind: ModelKind
  baseUrl?: string
  inputId?: string
  placeholder?: string
  inputClass?: string
}>(), {
  baseUrl: '',
  inputId: undefined,
  placeholder: 'Choose or type a model ID',
  inputClass: 'w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50',
})

const MAX_OPTIONS = 200
const BASE_URL_DEBOUNCE_MS = 600

const isOpen = ref(false)
const filter = ref('')
const activeIndex = ref(-1)
const listId = `model-list-${Math.random().toString(36).slice(2, 9)}`
let debounceTimer: ReturnType<typeof setTimeout> | undefined

const entry = computed(() => getProviderModelsEntry(providerModelsKey(props.provider, props.kind, props.baseUrl)))
const models = computed(() => entry.value?.list?.models ?? [])
const isLoading = computed((): boolean => entry.value?.status === 'loading')

const filtered = computed(() => {
  const needle = filter.value.trim().toLowerCase()
  const matches = needle
    ? models.value.filter((m) => m.id.toLowerCase().includes(needle) || m.label.toLowerCase().includes(needle))
    : models.value
  return matches.slice(0, MAX_OPTIONS)
})

const isUnlisted = computed((): boolean => {
  const list = entry.value?.list
  if (!model.value || list?.source !== 'live') {
    return false
  }
  return !list.models.some((m) => m.id === model.value)
})

const status = computed((): { tone: 'muted' | 'warn'; text: string } => {
  const current = entry.value
  if (!current || current.status === 'loading') {
    return { tone: 'muted', text: 'Loading models…' }
  }
  if (current.status === 'error' || !current.list) {
    return { tone: 'warn', text: current.requestError }
  }
  const { source, error } = current.list
  const count = current.list.models.length
  if (source === 'live') {
    return { tone: 'muted', text: `${count} models available from the provider.` }
  }
  if (source === 'static') {
    return { tone: 'muted', text: 'Built-in list — this provider offers no model listing.' }
  }
  return { tone: 'warn', text: `Live list unavailable: ${error} Showing built-in defaults.` }
})

function load(refresh = false): void {
  if (props.provider) {
    loadProviderModels(props.provider, props.kind, { baseUrl: props.baseUrl, refresh })
  }
}

function open(): void {
  filter.value = ''
  activeIndex.value = -1
  isOpen.value = true
}

function onInput(event: Event): void {
  model.value = (event.target as HTMLInputElement).value
  filter.value = model.value
  activeIndex.value = -1
  isOpen.value = true
}

function choose(id: string): void {
  model.value = id
  isOpen.value = false
}

function move(step: number): void {
  if (!isOpen.value) {
    open()
    return
  }
  const count = filtered.value.length
  if (count === 0) {
    return
  }
  activeIndex.value = (activeIndex.value + step + count) % count
}

function onEnter(event: KeyboardEvent): void {
  const option = filtered.value[activeIndex.value]
  if (!isOpen.value || !option) {
    return
  }
  event.preventDefault()
  choose(option.id)
}

watch(() => [props.provider, props.kind] as const, () => load(), { immediate: true })
watch(() => props.baseUrl, () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => load(), BASE_URL_DEBOUNCE_MS)
})
onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<template>
  <div class="space-y-1.5">
    <div class="relative">
      <input
        :id="props.inputId"
        :value="model"
        type="text"
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        :aria-expanded="isOpen"
        :aria-controls="listId"
        :aria-activedescendant="activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined"
        :placeholder="props.placeholder"
        :class="props.inputClass"
        @focus="open"
        @blur="isOpen = false"
        @input="onInput"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter="onEnter"
        @keydown.esc="isOpen = false"
      />
      <ChevronDown class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
      <ul
        v-if="isOpen && filtered.length > 0"
        :id="listId"
        role="listbox"
        class="absolute z-30 mt-1 w-full max-h-64 overflow-y-auto rounded-xl border border-white/10 bg-[#0a111c] shadow-2xl py-1"
      >
        <li
          v-for="(option, index) in filtered"
          :id="`${listId}-${index}`"
          :key="option.id"
          role="option"
          :aria-selected="option.id === model"
          class="px-4 py-2 cursor-pointer flex items-baseline justify-between gap-3"
          :class="index === activeIndex ? 'bg-white/10' : option.id === model ? 'bg-white/5' : 'hover:bg-white/5'"
          @mousedown.prevent="choose(option.id)"
        >
          <span class="text-sm font-mono text-white truncate">{{ option.id }}</span>
          <span v-if="option.label !== option.id" class="text-[11px] text-slate-500 truncate">{{ option.label }}</span>
        </li>
      </ul>
    </div>
    <div class="flex items-start justify-between gap-3">
      <p class="text-[11px] leading-snug" :class="status.tone === 'warn' ? 'text-amber-400' : 'text-slate-500'">
        {{ status.text }}
        <span v-if="isUnlisted" class="block text-amber-400">
          "{{ model }}" is not in the provider's list — it will be used as entered.
        </span>
      </p>
      <button
        type="button"
        class="shrink-0 flex items-center gap-1 text-[11px] text-slate-400 hover:text-white disabled:opacity-40"
        title="Reload the model list from the provider"
        :disabled="isLoading || !props.provider"
        @click="load(true)"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        Reload
      </button>
    </div>
  </div>
</template>
