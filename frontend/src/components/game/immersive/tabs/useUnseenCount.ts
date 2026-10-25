import { computed, ref, watch } from 'vue'

/**
 * Tracks how many entries of a growing list the player has not looked at yet.
 *
 * The first non-empty value (history loaded on session open) counts as seen; entries
 * arriving afterwards stay unseen until the owning tab is active.
 */
export function useUnseenCount(count: () => number, isActive: () => boolean) {
  const seenCount = ref(count())
  /** Seen count at the moment the tab was last opened — lets the panel highlight new entries. */
  const seenAtActivation = ref(seenCount.value)
  let primed = seenCount.value > 0

  watch(isActive, (active) => {
    if (active) {
      seenAtActivation.value = seenCount.value
    }
  })

  watch(
    [count, isActive],
    ([current, active]) => {
      if (!primed) {
        primed = current > 0
        seenCount.value = current
        seenAtActivation.value = current
        return
      }
      if (active || current < seenCount.value) {
        seenCount.value = current
      }
    },
    { flush: 'post' },
  )

  const unseen = computed(() => Math.max(0, count() - seenCount.value))

  return { unseen, seenAtActivation }
}
