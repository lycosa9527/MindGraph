/**
 * Stacking for Swiss glass cards vs Element Plus vs canvas node chrome.
 *
 * `.swiss-glass-card-overlay` is z-index 4000. Element Plus popups start near 2000,
 * so a menu or confirm opened from a full-screen card paints underneath it.
 * Full-screen cards register here; confirms and prompts rise only while one is open.
 *
 * Selected-node chrome is Teleported to `body` (floating toolbar 5000, poppers
 * 5100). Canvas dialogs opt into `.mm-above-node-chrome` so their overlay sits
 * at `SWISS_GLASS_CANVAS_DIALOG_Z` (keep in sync with swissGlassControls.css).
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

const openFullScreenCards = ref(0)

export function pushFullScreenGlassCard(): () => void {
  openFullScreenCards.value += 1
  let released = false
  return () => {
    if (released) {
      return
    }
    released = true
    openFullScreenCards.value -= 1
  }
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
  if (!dialogOpen || openFullScreenCards.value < 1) {
    return undefined
  }
  return SWISS_GLASS_CARD_DIALOG_Z
}

/** Call from setup. `active` is read inside the watcher so it stays reactive. */
export function bindFullScreenGlassCard(active: () => boolean): void {
  let release: (() => void) | null = null
  const sync = (on: boolean): void => {
    if (on && !release) {
      release = pushFullScreenGlassCard()
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

export function useGlassCardDialogZIndex(
  dialogOpen: () => boolean
): ComputedRef<number | undefined> {
  return computed(() => glassCardDialogZIndex(dialogOpen()))
}
