/**
 * Stacking for Swiss glass cards vs Element Plus.
 *
 * `.swiss-glass-card-overlay` is z-index 4000. Element Plus popups start near 2000,
 * so a menu or confirm opened from a full-screen card paints underneath it.
 * Full-screen cards register here; confirms and prompts rise only while one is open.
 */
import { type ComputedRef, computed, onBeforeUnmount, ref, watch } from 'vue'

/** Keep in sync with `.swiss-glass-card-overlay` in swissGlassControls.css. */
export const SWISS_GLASS_CARD_Z = 4000

/** Teleported menus inside a card. Stays under the confirm layer. */
export const SWISS_GLASS_CARD_POPPER_Z = 4100

/** Confirm / prompt while a full-screen card is open. */
export const SWISS_GLASS_CARD_DIALOG_Z = 4200

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
