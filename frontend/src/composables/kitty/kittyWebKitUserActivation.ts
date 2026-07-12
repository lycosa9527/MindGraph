/**
 * WebKit / HTML user-activation helpers for Kitty mic PTT.
 *
 * Canonical references:
 * - WebKit: https://webkit.org/blog/13862/the-user-activation-api/
 * - HTML: activation-triggering input events
 * - WebKit capturing unlock: AudioContext may start while getUserMedia is active
 *   (https://bugs.webkit.org/show_bug.cgi?id=180680)
 *
 * Activation-triggering events (WebKit blog + HTML):
 * - keydown (except Escape / reserved keys)
 * - mousedown
 * - pointerdown only when pointerType === "mouse"
 * - pointerup when pointerType !== "mouse" (touch / pen)
 * - touchend
 *
 * Touch pointerdown is NOT activation-triggering. Do not rely on it to unlock
 * Web Audio. Web Audio in WebKit also honors sticky activation after any prior
 * qualifying gesture on the page.
 */

export function hasStickyUserActivation(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const activation = (
    navigator as Navigator & {
      userActivation?: { hasBeenActive?: boolean; isActive?: boolean }
    }
  ).userActivation
  return activation?.hasBeenActive === true || activation?.isActive === true
}

export function isActivationTriggeringEvent(ev: Event): boolean {
  const type = ev.type
  if (type === 'keydown') {
    const keyEvent = ev as KeyboardEvent
    return keyEvent.key !== 'Escape'
  }
  if (type === 'mousedown' || type === 'click' || type === 'touchend') {
    return true
  }
  if (type === 'pointerdown') {
    return (ev as PointerEvent).pointerType === 'mouse'
  }
  if (type === 'pointerup') {
    return (ev as PointerEvent).pointerType !== 'mouse'
  }
  return false
}

/** True when this pointerdown itself grants transient activation (mouse only). */
export function pointerDownGrantsActivation(ev: PointerEvent): boolean {
  return ev.pointerType === 'mouse'
}

/** True when this pointerup itself grants transient activation (touch/pen). */
export function pointerUpGrantsActivation(ev: PointerEvent): boolean {
  return ev.pointerType !== 'mouse'
}
