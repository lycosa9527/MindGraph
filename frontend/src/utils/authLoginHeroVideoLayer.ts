/**
 * `/auth` COS hero video must stay under teleported modals (test-server banner, etc.).
 * Some Android WebViews paint `<video>` in a native layer above DOM z-index.
 */

/** Teleported or fixed overlays that must sit above the cinema clip. */
export const AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR = [
  '.swm-overlay',
  '.session-auth-overlay',
  '.swiss-glass-card-overlay:not(.swiss-glass-card-overlay--auth-split)',
  '.el-overlay',
  '.el-message-box__wrapper',
  '.tsec-login-layer',
].join(', ')

export function authLoginHeroNativeVideoLayerRisk(userAgent?: string): boolean {
  const ua =
    userAgent ??
    (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  return /Android/i.test(ua)
}

export function isAuthLoginHeroBlockingOverlayElement(element: Element): boolean {
  if (!(element instanceof HTMLElement)) {
    return false
  }
  if (element.matches('.swiss-glass-card-overlay--auth-split')) {
    return false
  }
  if (!element.matches(AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR)) {
    return false
  }
  const style = getComputedStyle(element)
  return style.display !== 'none' && style.visibility !== 'hidden'
}

export function documentHasAuthLoginHeroBlockingOverlay(doc?: Document): boolean {
  if (typeof document === 'undefined' && doc === undefined) {
    return false
  }
  const root = doc ?? document
  if (!root.querySelectorAll) {
    return false
  }
  const nodes = root.querySelectorAll(AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR)
  for (const node of nodes) {
    if (isAuthLoginHeroBlockingOverlayElement(node)) {
      return true
    }
  }
  return false
}
