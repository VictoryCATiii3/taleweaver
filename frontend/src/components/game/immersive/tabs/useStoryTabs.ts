import { computed, ref, watch, type Ref } from 'vue'
import type { ChatMessage } from '@/types'
import type { StoryTabId } from './types'
import { useUnseenCount } from './useUnseenCount'

type StoryTabsSource = {
  sceneExits: () => any[] | undefined
  items: () => any[] | undefined
  systemMessages: Ref<ChatMessage[]>
}

/** Active story tab, per-tab counts and "new entries" markers for the immersive view. */
export function useStoryTabs(source: StoryTabsSource) {
  const activeStoryTab = ref<StoryTabId>('story')
  const sceneExits = computed(() => source.sceneExits() ?? [])
  const sceneItems = computed(() => source.items() ?? [])
  const systemLog = source.systemMessages
  const hasLockedExits = computed(() => sceneExits.value.some((exit: any) => exit.is_locked))

  const { unseen: unseenSystem, seenAtActivation: systemSeenAtOpen } = useUnseenCount(
    () => systemLog.value.length,
    () => activeStoryTab.value === 'system'
  )
  const { unseen: unseenItems } = useUnseenCount(
    () => sceneItems.value.length,
    () => activeStoryTab.value === 'discoveries'
  )

  const tabCounts = computed<Record<StoryTabId, number>>(() => ({
    story: 1,
    passages: sceneExits.value.length,
    discoveries: sceneItems.value.length,
    system: systemLog.value.length,
  }))

  // A tab whose content disappeared (scene change, last item taken) falls back to the story.
  watch(tabCounts, (counts) => {
    if (!counts[activeStoryTab.value]) {
      activeStoryTab.value = 'story'
    }
  })

  function showStory() {
    activeStoryTab.value = 'story'
  }

  return {
    activeStoryTab,
    sceneExits,
    sceneItems,
    systemLog,
    hasLockedExits,
    unseenSystem,
    unseenItems,
    systemSeenAtOpen,
    showStory,
  }
}
