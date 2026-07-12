/**
 * Push-to-talk mic and Space-key handling for MobileKittyPage (Fun-ASR).
 *
 * iOS Safari requires getUserMedia/AudioContext to start inside the user-gesture
 * turn. We kick those off on pointerdown before awaiting WebSocket connect.
 * Never disable the mic button while connecting — disabling cancels the pointer
 * on iOS and aborts hold-to-talk.
 */
import { type Ref, onUnmounted, ref } from 'vue'

import {
  kickoffKittyMicGestureAssets,
  releaseKittyMicGestureAssets,
  type KittyMicGestureAssets,
} from '@/composables/kitty/useKittyFunAsrMic'

export interface UseMobileKittyMicPttFunAsr {
  listening: Ref<boolean>
  startListening: (gestureAssets?: KittyMicGestureAssets) => Promise<void>
  stopListening: () => void
}

export interface UseMobileKittyMicPttOptions {
  funAsr: UseMobileKittyMicPttFunAsr
  kittyServerEnabled: { value: boolean }
  micDenied: { value: boolean }
  showKeyboard: { value: boolean }
  connected: { value: boolean }
  ensureConnected: () => Promise<boolean>
  onMicDenied: () => void
  onMicAllowed: () => void
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
  } = options

  const voiceStartInFlight = ref(false)
  const pttPointerActive = ref(false)
  let spacePttActive = false
  let kittyMicKbBound = false
  let activePointerId: number | null = null
  let captureEl: HTMLElement | null = null
  let windowPointerBound = false

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
    if (captureEl.hasPointerCapture(activePointerId)) {
      try {
        captureEl.releasePointerCapture(activePointerId)
      } catch {
        /* ignore */
      }
    }
    captureEl = null
    activePointerId = null
  }

  async function beginKittyMicFromUser(
    gestureAssetsPromise?: Promise<KittyMicGestureAssets>
  ): Promise<void> {
    if (!kittyServerEnabled.value || micDenied.value) {
      if (gestureAssetsPromise) {
        void gestureAssetsPromise
          .then(releaseKittyMicGestureAssets)
          .catch(() => undefined)
      }
      return
    }
    if (funAsr.listening.value || voiceStartInFlight.value) {
      if (gestureAssetsPromise) {
        void gestureAssetsPromise
          .then(releaseKittyMicGestureAssets)
          .catch(() => undefined)
      }
      return
    }
    voiceStartInFlight.value = true
    let ownedAssets: KittyMicGestureAssets | undefined
    try {
      const ok = await ensureConnected()
      if (!ok || !isKittyMicHoldActive()) {
        if (gestureAssetsPromise) {
          try {
            ownedAssets = await gestureAssetsPromise
          } catch {
            ownedAssets = undefined
          }
        }
        return
      }
      if (gestureAssetsPromise) {
        ownedAssets = await gestureAssetsPromise
        if (!isKittyMicHoldActive()) {
          return
        }
        await funAsr.startListening(ownedAssets)
        ownedAssets = undefined
      } else {
        await funAsr.startListening()
      }
      if (!isKittyMicHoldActive()) {
        funAsr.stopListening()
      } else {
        onMicAllowed()
      }
    } catch {
      onMicDenied()
    } finally {
      if (ownedAssets) {
        releaseKittyMicGestureAssets(ownedAssets)
      }
      voiceStartInFlight.value = false
    }
  }

  function endKittyMicFromUser(): void {
    pttPointerActive.value = false
    spacePttActive = false
    unbindWindowPointerEnd()
    releasePointerCaptureSafe()
    if (funAsr.listening.value) {
      funAsr.stopListening()
    }
  }

  function finishPointerPtt(): void {
    pttPointerActive.value = false
    unbindWindowPointerEnd()
    releasePointerCaptureSafe()
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
    finishPointerPtt()
  }

  function onKittyMicPointerDown(ev: PointerEvent): void {
    if (ev.button !== 0) {
      return
    }
    // Do not gate on `connecting` — disabling/bailing mid-hold cancels iOS pointers.
    if (!kittyServerEnabled.value || micDenied.value) {
      return
    }
    if (pttPointerActive.value) {
      return
    }
    pttPointerActive.value = true
    activePointerId = ev.pointerId
    const el = ev.currentTarget
    if (el instanceof HTMLElement) {
      captureEl = el
      el.setPointerCapture(ev.pointerId)
    }
    ev.preventDefault()
    bindWindowPointerEnd()

    let gesturePromise: Promise<KittyMicGestureAssets>
    try {
      gesturePromise = kickoffKittyMicGestureAssets()
    } catch {
      finishPointerPtt()
      onMicDenied()
      return
    }
    void beginKittyMicFromUser(gesturePromise)
  }

  function onKittyMicPointerUp(ev: PointerEvent): void {
    if (activePointerId !== null && ev.pointerId !== activePointerId) {
      return
    }
    finishPointerPtt()
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
    let gesturePromise: Promise<KittyMicGestureAssets> | undefined
    try {
      gesturePromise = kickoffKittyMicGestureAssets()
    } catch {
      spacePttActive = false
      onMicDenied()
      return
    }
    void beginKittyMicFromUser(gesturePromise)
  }

  function onKittySpacePttKeyUp(ev: KeyboardEvent): void {
    if (ev.code !== 'Space' && ev.key !== ' ') {
      return
    }
    if (!spacePttActive) {
      return
    }
    spacePttActive = false
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

  function bindKittyMicKeyboard(): void {
    if (kittyMicKbBound || typeof window === 'undefined') {
      return
    }
    kittyMicKbBound = true
    window.addEventListener('keydown', onKittySpacePttKeyDown, true)
    window.addEventListener('keyup', onKittySpacePttKeyUp, true)
    document.addEventListener('visibilitychange', handleKittyVisibilityForMic)
  }

  function unbindKittyMicKeyboard(): void {
    if (!kittyMicKbBound || typeof window === 'undefined') {
      return
    }
    kittyMicKbBound = false
    window.removeEventListener('keydown', onKittySpacePttKeyDown, true)
    window.removeEventListener('keyup', onKittySpacePttKeyUp, true)
    document.removeEventListener('visibilitychange', handleKittyVisibilityForMic)
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
    bindKittyMicKeyboard,
    teardownMicPtt,
  }
}
