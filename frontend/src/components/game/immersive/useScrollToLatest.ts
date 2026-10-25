import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** Distance (px) from the bottom below which the feed counts as "at the latest message". */
const AT_BOTTOM_THRESHOLD_PX = 120

/**
 * Tracks whether a scroll container has content below the visible area and offers a smooth
 * jump to its end. Recomputes on scroll, on resize and whenever the content changes.
 */
export function useScrollToLatest(container: Ref<HTMLElement | null>) {
  const hasContentBelow = ref(false)
  let resizeObserver: ResizeObserver | null = null
  let mutationObserver: MutationObserver | null = null
  let frame = 0

  function measure() {
    frame = 0
    const el = container.value
    if (!el) {
      hasContentBelow.value = false
      return
    }
    hasContentBelow.value = el.scrollHeight - el.scrollTop - el.clientHeight > AT_BOTTOM_THRESHOLD_PX
  }

  function scheduleMeasure() {
    if (!frame) {
      frame = requestAnimationFrame(measure)
    }
  }

  function scrollToLatest() {
    const el = container.value
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }

  onMounted(() => {
    const el = container.value
    if (!el) {
      return
    }
    el.addEventListener('scroll', scheduleMeasure, { passive: true })
    resizeObserver = new ResizeObserver(scheduleMeasure)
    resizeObserver.observe(el)
    mutationObserver = new MutationObserver(scheduleMeasure)
    mutationObserver.observe(el, { childList: true, subtree: true, characterData: true })
    scheduleMeasure()
  })

  onBeforeUnmount(() => {
    container.value?.removeEventListener('scroll', scheduleMeasure)
    resizeObserver?.disconnect()
    mutationObserver?.disconnect()
    if (frame) {
      cancelAnimationFrame(frame)
    }
  })

  return { hasContentBelow, scrollToLatest }
}
