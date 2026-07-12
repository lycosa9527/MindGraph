/**
 * Push-to-talk for MobileKittyPage (Fun-ASR).
 *
 * Follows WebKit / HTML user-activation rules:
 * https://webkit.org/blog/13862/the-user-activation-api/
 *
 * - Mouse: pointerdown is activation-triggering → warm/bless here.
 * - Touch/pen: pointerdown is NOT activation-triggering; pointerup / touchend are.
 *   We still start getUserMedia on pointerdown (same call stack), then re-bless on
 *   pointerup/touchend and rely on sticky activation + capturing unlock
 *   (WebKit bug 180680) so PCM can flow during the hold after the stream is live.
 * - Space keydown is activation-triggering.
 * - Never disable the mic button while connecting (iOS pointercancel).
 */
import { type Ref, onUnmounted, ref } from 'vue'

import {
  hasStickyUserActivation,
  isActivationTriggeringEvent,
  pointerDownGrantsActivation,
  pointerUpGrantsActivation,
} from '@/composables/kitty/kittyWebKitUserActivation'

export interface UseMobileKittyMicPttFunAsr {
  listening: Ref<boolean>
  prepareMicFromUserGesture: () => Promise<boolean>
  blessFromUserActivation: () => void
  startListening: () => Promise<
    | { ok: true; utteranceId: string }
    | { ok: false; reason: 'not_connected' | 'mic_denied' | 'context_dead' }
  >
  stopListening: () => void
}

export type MobileKittyPttAbortReason =
  | 'released_early'
  | 'connect_failed'
  | 'mic_denied'
  | 'context_dead'
  | 'start_failed'

export interface UseMobileKittyMicPttOptions {
  funAsr: UseMobileKittyMicPttFunAsr
  kittyServerEnabled: { value: boolean }
  micDenied: { value: boolean }
  showKeyboard: { value: boolean }
  connected: { value: boolean }
  ensureConnected: () => Promise<boolean>
  onMicDenied: () => void
  onMicAllowed: () => void
  /** Fired when PTT warm-up completes but listening never starts. */
  onPttAborted?: (reason: MobileKittyPttAbortReason) => void
  /** Optional trace for on-device consoles (Eruda). */
  onPttDebug?: (detail: string) => void
}

export function useMobileKittyMicPtt(options: UseMobileKittyMicPttOptions) {
  const {
    funAsr,
    kittyServerEnabled,
    micDenied,
    showKeyboard,
    connected,
    ensureConnected,
    onMicDenied,
    onMicAllowed,
    onPttAborted,
    onPttDebug,
  } = options

  function pttDebug(detail: string): void {
    onPttDebug?.(detail)
  }

  const voiceStartInFlight = ref(false)
  const pttPointerActive = ref(false)
  let spacePttActive = false
  let kittyMicKbBound = false
  let activationPrimeBound = false
  let activePointerId: number | null = null
  let captureEl: HTMLElement | null = null
  let windowPointerBound = false
  /** Bumped on every pointer/space end so in-flight startListening is abandoned. */
  let pttGeneration = 0

  function isKittyTextInputTarget(): boolean {
    if (!showKeyboard.value || !connected.value) {
      return false
    }
    const el = document.activeElement
    if (!el) {
      return false
    }
    if (el.tagName === 'TEXTAREA') {
      return true
    }
    if (el.tagName !== 'INPUT') {
      return false
    }
    const input = el as HTMLInputElement
    const typ = (input.type ?? 'text').toLowerCase()
    if (typ === 'checkbox' || typ === 'radio' || typ === 'file' || typ === 'button') {
      return false
    }
    return true
  }

  function shouldReserveSpaceForTarget(ev: Event): boolean {
    const target = ev.target
    if (!(target instanceof HTMLElement)) {
      return false
    }
    if (target.isContentEditable || target.closest('[contenteditable="true"]')) {
      return true
    }
    if (target.closest('[data-kitty-mic-ptt]')) {
      return false
    }
    const tag = target.tagName
    if (tag === 'TEXTAREA' || tag === 'SELECT') {
      return true
    }
    if (tag === 'BUTTON') {
      return true
    }
    if (tag === 'INPUT') {
      const input = target as HTMLInputElement
      const typ = (input.type ?? 'text').toLowerCase()
      if (typ === 'checkbox' || typ === 'radio') {
        return true
      }
      if (typ === 'file' || typ === 'hidden') {
        return false
      }
      return true
    }
    return false
  }

  function isKittyMicHoldActive(): boolean {
    return pttPointerActive.value || spacePttActive
  }

  function unbindWindowPointerEnd(): void {
    if (!windowPointerBound || typeof window === 'undefined') {
      return
    }
    windowPointerBound = false
    window.removeEventListener('pointerup', onWindowPointerEnd)
    window.removeEventListener('pointercancel', onWindowPointerEnd)
  }

  function bindWindowPointerEnd(): void {
    if (windowPointerBound || typeof window === 'undefined') {
      return
    }
    windowPointerBound = true
    window.addEventListener('pointerup', onWindowPointerEnd)
    window.addEventListener('pointercancel', onWindowPointerEnd)
  }

  function releasePointerCaptureSafe(): void {
    if (!captureEl || activePointerId === null) {
      captureEl = null
      activePointerId = null
      return
    }
    try {
      if (captureEl.hasPointerCapture(activePointerId)) {
        captureEl.releasePointerCapture(activePointerId)
      }
    } catch {
      /* Pointer capture is optional; WebKit may reject stale pointer ids. */
    }
    captureEl = null
    activePointerId = null
  }

  /** Bless only inside activation-triggering events (WebKit list). */
  function blessIfActivationTriggering(ev: Event): void {
    if (!isActivationTriggeringEvent(ev)) {
      return
    }
    funAsr.blessFromUserActivation()
  }

  async function beginKittyMicFromUser(warmPromise: Promise<boolean>): Promise<void> {
    if (!kittyServerEnabled.value || micDenied.value) {
      pttDebug('begin skip:disabled')
      return
    }
    // A prior startListening hang used to leave voiceStartInFlight stuck true so
    // later holds only flipped hold:1 / LED and never sent asr_start.
    if (funAsr.listening.value) {
      pttDebug('begin skip:already_listening')
      return
    }
    const generation = pttGeneration
    voiceStartInFlight.value = true
    pttDebug(`begin gen=${generation}`)
    try {
      // Keep mic warm and WS connect in parallel (warm already started on pointerdown).
      // Connection timeout and socket ownership live in useKittyAgent. A second
      // timer here could report failure while a scope replacement socket had
      // already completed its server handshake.
      const [connectedOk, warmOk] = await Promise.all([ensureConnected(), warmPromise])
      if (generation !== pttGeneration || !isKittyMicHoldActive()) {
        onPttAborted?.('released_early')
        return
      }
      if (!warmOk) {
        onMicDenied()
        onPttAborted?.('mic_denied')
        return
      }
      if (!connectedOk) {
        onPttAborted?.('connect_failed')
        return
      }
      // Sticky / capturing unlock may have made the context runnable while we awaited.
      funAsr.blessFromUserActivation()
      const started = await funAsr.startListening()
      if (generation !== pttGeneration || !isKittyMicHoldActive()) {
        funAsr.stopListening()
        pttDebug('stop:released_during_start')
        return
      }
      if (!started.ok) {
        if (started.reason === 'mic_denied') {
          onMicDenied()
          onPttAborted?.('mic_denied')
          return
        }
        if (started.reason === 'context_dead') {
          onPttAborted?.('context_dead')
          return
        }
        onPttAborted?.('connect_failed')
        return
      }
      onMicAllowed()
      pttDebug(`listening utt=${started.utteranceId.slice(0, 12)}`)
    } catch (error) {
      const message = error instanceof Error ? error.message.toLowerCase() : ''
      const isPermission =
        message.includes('permission') ||
        message.includes('notallowed') ||
        message.includes('denied')
      if (isPermission) {
        onMicDenied()
        onPttAborted?.('mic_denied')
      } else {
        onPttAborted?.('start_failed')
      }
    } finally {
      if (generation === pttGeneration) {
        voiceStartInFlight.value = false
      }
    }
  }

  function endKittyMicFromUser(): void {
    pttGeneration += 1
    pttPointerActive.value = false
    spacePttActive = false
    voiceStartInFlight.value = false
    unbindWindowPointerEnd()
    releasePointerCaptureSafe()
    if (funAsr.listening.value) {
      funAsr.stopListening()
    }
  }

  function finishPointerPtt(ev?: PointerEvent): void {
    if (ev && pointerUpGrantsActivation(ev)) {
      // Touch/pen pointerup is activation-triggering — unlock Web Audio here.
      blessIfActivationTriggering(ev)
    }
    const wasActive = pttPointerActive.value
    pttGeneration += 1
    pttPointerActive.value = false
    voiceStartInFlight.value = false
    unbindWindowPointerEnd()
    releasePointerCaptureSafe()
    if (wasActive) {
      pttDebug(`up type=${ev?.pointerType ?? '—'} cancel=${ev?.type === 'pointercancel' ? 1 : 0}`)
    }
    if (funAsr.listening.value) {
      funAsr.stopListening()
    }
  }

  function onWindowPointerEnd(ev: PointerEvent): void {
    if (!pttPointerActive.value) {
      return
    }
    if (activePointerId !== null && ev.pointerId !== activePointerId) {
      return
    }
    finishPointerPtt(ev)
  }

  function isPrimaryPointerDown(ev: PointerEvent): boolean {
    // Mouse: only primary button. Touch/pen: WebKit has historically reported
    // incorrect `button` values — accept the contact regardless.
    if (ev.pointerType === 'mouse') {
      return ev.button === 0
    }
    return ev.button === 0 || ev.button === -1 || ev.buttons > 0 || ev.isPrimary !== false
  }

  function onKittyMicPointerDown(ev: PointerEvent): void {
    if (!isPrimaryPointerDown(ev)) {
      pttDebug(`down skip:button=${ev.button} type=${ev.pointerType}`)
      return
    }
    if (!kittyServerEnabled.value || micDenied.value) {
      pttDebug(
        `down skip:flag server=${kittyServerEnabled.value ? 1 : 0} denied=${micDenied.value ? 1 : 0}`
      )
      return
    }
    if (pttPointerActive.value) {
      pttDebug('down skip:already_held')
      return
    }
    pttPointerActive.value = true
    activePointerId = ev.pointerId
    pttDebug(`down type=${ev.pointerType} btn=${ev.button} id=${ev.pointerId}`)
    ev.preventDefault()
    bindWindowPointerEnd()

    // Start required microphone work before optional pointer capture. WebKit can
    // throw from setPointerCapture(); that must never prevent ASR warm-up.
    // Mouse pointerdown grants activation; touch relies on sticky/capturing/pointerup.
    let warmPromise: Promise<boolean>
    try {
      warmPromise = funAsr.prepareMicFromUserGesture()
      if (pointerDownGrantsActivation(ev) || hasStickyUserActivation()) {
        funAsr.blessFromUserActivation()
      }
    } catch {
      finishPointerPtt()
      onMicDenied()
      return
    }

    const el = ev.currentTarget
    if (el instanceof HTMLElement) {
      captureEl = el
      try {
        el.setPointerCapture(ev.pointerId)
      } catch {
        /* Window pointerup remains the release fallback on WebKit. */
      }
    }
    void beginKittyMicFromUser(warmPromise)
  }

  function onKittyMicPointerUp(ev: PointerEvent): void {
    if (activePointerId !== null && ev.pointerId !== activePointerId) {
      return
    }
    finishPointerPtt(ev)
  }

  /** WebKit lists touchend explicitly as activation-triggering. */
  function onKittyMicTouchEnd(ev: TouchEvent): void {
    if (!pttPointerActive.value) {
      return
    }
    blessIfActivationTriggering(ev)
  }

  function onKittySpacePttKeyDown(ev: KeyboardEvent): void {
    if (ev.code !== 'Space' && ev.key !== ' ') {
      return
    }
    if (ev.repeat || isKittyTextInputTarget()) {
      return
    }
    if (shouldReserveSpaceForTarget(ev)) {
      return
    }
    if (!kittyServerEnabled.value || micDenied.value) {
      return
    }
    ev.preventDefault()
    if (spacePttActive) {
      return
    }
    spacePttActive = true
    // keydown is activation-triggering.
    let warmPromise: Promise<boolean>
    try {
      warmPromise = funAsr.prepareMicFromUserGesture()
    } catch {
      spacePttActive = false
      onMicDenied()
      return
    }
    void beginKittyMicFromUser(warmPromise)
  }

  function onKittySpacePttKeyUp(ev: KeyboardEvent): void {
    if (ev.code !== 'Space' && ev.key !== ' ') {
      return
    }
    if (!spacePttActive) {
      return
    }
    pttGeneration += 1
    spacePttActive = false
    voiceStartInFlight.value = false
    if (funAsr.listening.value) {
      funAsr.stopListening()
    }
  }

  function handleKittyVisibilityForMic(): void {
    if (!document.hidden) {
      return
    }
    endKittyMicFromUser()
  }

  /**
   * Page-level prime: re-bless an already-warmed AudioContext on activation
   * events. Do not call getUserMedia here — unrelated taps must not prompt.
   */
  function onActivationPrimeEvent(ev: Event): void {
    if (!kittyServerEnabled.value || micDenied.value) {
      return
    }
    if (!isActivationTriggeringEvent(ev)) {
      return
    }
    funAsr.blessFromUserActivation()
  }

  function bindMicActivationPrime(): void {
    if (activationPrimeBound || typeof window === 'undefined') {
      return
    }
    activationPrimeBound = true
    // Exact WebKit activation-triggering set (plus click, which follows a gesture).
    window.addEventListener('keydown', onActivationPrimeEvent, true)
    window.addEventListener('mousedown', onActivationPrimeEvent, true)
    window.addEventListener('pointerdown', onActivationPrimeEvent, true)
    window.addEventListener('pointerup', onActivationPrimeEvent, true)
    window.addEventListener('touchend', onActivationPrimeEvent, true)
    window.addEventListener('click', onActivationPrimeEvent, true)
  }

  function unbindMicActivationPrime(): void {
    if (!activationPrimeBound || typeof window === 'undefined') {
      return
    }
    activationPrimeBound = false
    window.removeEventListener('keydown', onActivationPrimeEvent, true)
    window.removeEventListener('mousedown', onActivationPrimeEvent, true)
    window.removeEventListener('pointerdown', onActivationPrimeEvent, true)
    window.removeEventListener('pointerup', onActivationPrimeEvent, true)
    window.removeEventListener('touchend', onActivationPrimeEvent, true)
    window.removeEventListener('click', onActivationPrimeEvent, true)
  }

  function bindKittyMicKeyboard(): void {
    if (kittyMicKbBound || typeof window === 'undefined') {
      return
    }
    kittyMicKbBound = true
    window.addEventListener('keydown', onKittySpacePttKeyDown, true)
    window.addEventListener('keyup', onKittySpacePttKeyUp, true)
    document.addEventListener('visibilitychange', handleKittyVisibilityForMic)
    bindMicActivationPrime()
  }

  function unbindKittyMicKeyboard(): void {
    if (!kittyMicKbBound || typeof window === 'undefined') {
      return
    }
    kittyMicKbBound = false
    window.removeEventListener('keydown', onKittySpacePttKeyDown, true)
    window.removeEventListener('keyup', onKittySpacePttKeyUp, true)
    document.removeEventListener('visibilitychange', handleKittyVisibilityForMic)
    unbindMicActivationPrime()
  }

  function teardownMicPtt(): void {
    unbindKittyMicKeyboard()
    endKittyMicFromUser()
    voiceStartInFlight.value = false
  }

  onUnmounted(() => {
    teardownMicPtt()
  })

  return {
    voiceStartInFlight,
    pttPointerActive,
    onKittyMicPointerDown,
    onKittyMicPointerUp,
    onKittyMicTouchEnd,
    bindKittyMicKeyboard,
    teardownMicPtt,
  }
}
