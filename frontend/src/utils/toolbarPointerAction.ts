/**
 * Touch taps inside a transformed menu often never emit `click`.
 * Apply on pointerup for touch and pen. The click that follows would
 * toggle bold/italic/underline a second time, so it is ignored.
 * Mouse keeps the click path.
 */
export function createToolbarPointerAction(windowMs = 700): {
  onPointerUp: (event: PointerEvent, action: () => void) => void
  onClick: (action: () => void) => void
} {
  let touchAppliedAt = 0

  return {
    onPointerUp(event, action) {
      if (event.pointerType === 'mouse') return
      touchAppliedAt = performance.now()
      action()
    },
    onClick(action) {
      if (touchAppliedAt > 0 && performance.now() - touchAppliedAt < windowMs) return
      action()
    },
  }
}
