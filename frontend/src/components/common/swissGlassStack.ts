/**
 * Stacking for Swiss glass cards vs Element Plus vs canvas node chrome.
 *
 * `.swiss-glass-card-overlay` is z-index 4000. Element Plus popups start near 2000,
 * so a menu or confirm opened from a full-screen card paints underneath it.
 * Full-screen cards register here; confirms and prompts rise only while one is open.
 *
 * Selected-node chrome is Teleported to `body` (floating toolbar 5000, poppers
 * 5100). In-page sheets (mobile brainstorm / parking lot) cannot stack above
 * that, so they hide chrome via `useCanvasNodeChromeOverlayGate`. Body dialogs
 * opt into `.mm-above-node-chrome` or use `SWISS_GLASS_CANVAS_DIALOG_Z`
 * (keep in sync with swissGlassControls.css / mind-map-side-rail-panel.css).
 */
import { type ComputedRef, computed, onBeforeUnmount, ref, watch } from 'vue'

/** Keep in sync with `.swiss-glass-card-overlay` in swissGlassControls.css. */
export const SWISS_GLASS_CARD_Z = 4000

/** Teleported menus inside a card. Stays under the confirm layer. */
export const SWISS_GLASS_CARD_POPPER_Z = 4100

/** Confirm / prompt while a full-screen card is open. */
export const SWISS_GLASS_CARD_DIALOG_Z = 4200

/**
 * Teleported selected-node chrome. Toolbar poppers use `!important` at this
 * band, so canvas dialog overlays must use the same (`SWISS_GLASS_CANVAS_DIALOG_Z`).
 */
export const CANVAS_NODE_CHROME_Z = {
  FLOATING_TOOLBAR: 5000,
  FLOATING_TOOLBAR_PANEL: 5010,
  FLOATING_TOOLBAR_POPPER: 5100,
} as const

/** Marker on canvas ElDialogs whose overlay must cover node chrome. */
export const MM_ABOVE_NODE_CHROME_CLASS = 'mm-above-node-chrome'

/** Canvas dialog overlay. Below context menu (10000) and MathLive keyboard. */
export const SWISS_GLASS_CANVAS_DIALOG_Z = CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR_POPPER + 100

type OpenCountLayer = {
  count: { readonly value: number }
  push: () => () => void
  bind: (active: () => boolean) => void
}

function createOpenCountLayer(): OpenCountLayer {
  const count = ref(0)
  const push = (): (() => void) => {
    count.value += 1
    let released = false
    return () => {
      if (released) {
        return
      }
      released = true
      count.value -= 1
    }
  }
  const bind = (active: () => boolean): void => {
    let release: (() => void) | null = null
    const sync = (on: boolean): void => {
      if (on && !release) {
        release = push()
        return
      }
      if (!on && release) {
        release()
        release = null
      }
    }
    watch(active, sync, { immediate: true })
    onBeforeUnmount(() => {
      sync(false)
    })
  }
  return { count, push, bind }
}

const fullScreenCards = createOpenCountLayer()
const coveringOverlays = createOpenCountLayer()

export function pushFullScreenGlassCard(): () => void {
  return fullScreenCards.push()
}

/** Body dialog / card that must not sit under teleported node chrome. */
export function pushCanvasCoveringOverlay(): () => void {
  return coveringOverlays.push()
}

export function canvasCoveringOverlayOpen(): boolean {
  return coveringOverlays.count.value > 0
}

/** Body-level card overlay. Embedded `/auth` and training hosts are not this layer. */
export function glassCardHoldsPopupLayer(options: {
  hostIsBody: boolean
  teleportDisabled: boolean
  overlayClass: string
}): boolean {
  if (!options.hostIsBody || options.teleportDisabled) {
    return false
  }
  if (options.overlayClass.includes('swiss-glass-card-overlay--auth-split')) {
    return false
  }
  if (options.overlayClass.includes('swiss-glass-card-overlay--contained')) {
    return false
  }
  return true
}

export function glassCardDialogZIndex(dialogOpen: boolean): number | undefined {
  if (!dialogOpen || fullScreenCards.count.value < 1) {
    return undefined
  }
  return SWISS_GLASS_CARD_DIALOG_Z
}

/** Call from setup. `active` is read inside the watcher so it stays reactive. */
export function bindFullScreenGlassCard(active: () => boolean): void {
  fullScreenCards.bind(active)
}

/** Call from setup. Hides teleported node chrome while the overlay is open. */
export function bindCanvasCoveringOverlay(active: () => boolean): void {
  coveringOverlays.bind(active)
}

export function useGlassCardDialogZIndex(
  dialogOpen: () => boolean
): ComputedRef<number | undefined> {
  return computed(() => glassCardDialogZIndex(dialogOpen()))
}
