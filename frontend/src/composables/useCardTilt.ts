import { ref, type Ref } from 'vue'

/**
 * Pointer-driven 3D tilt with a moving glare highlight.
 * Writes CSS variables (--tilt-x, --tilt-y, --glare-x, --glare-y) on the element;
 * the styling lives in portal-theme.css. Disabled for touch input and reduced motion.
 */
export function useCardTilt(maxDegrees = 6): {
  tiltRef: Ref<HTMLElement | null>
  onPointerMove: (event: PointerEvent) => void
  onPointerLeave: () => void
} {
  const tiltRef = ref<HTMLElement | null>(null)

  function prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  }

  function onPointerMove(event: PointerEvent): void {
    const el = tiltRef.value
    if (!el || event.pointerType !== 'mouse' || prefersReducedMotion()) return
    const rect = el.getBoundingClientRect()
    const px = (event.clientX - rect.left) / rect.width
    const py = (event.clientY - rect.top) / rect.height
    el.style.setProperty('--tilt-x', `${((0.5 - py) * maxDegrees).toFixed(2)}deg`)
    el.style.setProperty('--tilt-y', `${((px - 0.5) * maxDegrees).toFixed(2)}deg`)
    el.style.setProperty('--glare-x', `${(px * 100).toFixed(1)}%`)
    el.style.setProperty('--glare-y', `${(py * 100).toFixed(1)}%`)
  }

  function onPointerLeave(): void {
    const el = tiltRef.value
    if (!el) return
    el.style.setProperty('--tilt-x', '0deg')
    el.style.setProperty('--tilt-y', '0deg')
  }

  return { tiltRef, onPointerMove, onPointerLeave }
}
