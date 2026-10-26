<script setup lang="ts">
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { testService } from '@/services/testService'
import { wizardStyles } from './wizardPresets'

const props = defineProps<{ testKey: string }>()

const result = computed(() => testService.testResults.value[props.testKey])
</script>

<template>
  <div v-if="result" class="space-y-2">
    <p v-if="result.status === 'loading'" class="flex items-center gap-2 text-xs text-slate-400">
      <Loader2 class="w-4 h-4 animate-spin" /> {{ result.message }}
    </p>
    <p v-else :class="result.status === 'success' ? wizardStyles.success : wizardStyles.error">
      {{ result.message }}
    </p>
    <img
      v-if="result.image_url"
      :src="result.image_url"
      alt="Test image"
      class="w-40 h-40 object-cover rounded-xl border border-white/10"
    />
  </div>
</template>
