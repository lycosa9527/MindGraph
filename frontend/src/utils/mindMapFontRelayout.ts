/**
 * Restack once the canvas font is actually available.
 * A full reload already has that font, so the first measure matches the paint.
 * A live session often measures earlier and then keeps those columns.
 */
import { shallowRef } from 'vue'

let fontRelayoutPending = false

/** One live layout may measure again. The computed reads this so the pass is not cached. */
const mindMapFreshWrapStamp = shallowRef(false)

function requestFreshMindMapWrapStamp(): void {
  mindMapFreshWrapStamp.value = true
}

export function peekFreshMindMapWrapStamp(): boolean {
  return mindMapFreshWrapStamp.value
}

export function clearFreshMindMapWrapStamp(): void {
  if (!mindMapFreshWrapStamp.value) return
  mindMapFreshWrapStamp.value = false
}

export function scheduleMindMapRelayoutWhenFontsLoad(schedule: () => void): void {
  if (typeof document === 'undefined' || document.fonts == null) return
  if (document.fonts.status === 'loaded') return
  if (fontRelayoutPending) return
  fontRelayoutPending = true
  const run = (): void => {
    if (!fontRelayoutPending) return
    fontRelayoutPending = false
    requestFreshMindMapWrapStamp()
    schedule()
  }
  void document.fonts.ready.then(run)
  document.fonts.addEventListener('loadingdone', run, { once: true })
}
