/**
 * Push-to-talk mic and Space-key handling for MobileKittyPage.
 */
import { onUnmounted, ref } from 'vue'

import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'

export interface UseMobileKittyMicPttOptions {
  kitty: ReturnType<typeof useKittyAgent>
  kittyServerEnabled: { value: boolean }
  connecting: { value: boolean }
  micDenied: { value: boolean }
  showKeyboard: { value: boolean }
  connected: { value: boolean }
  ensureConnected: () => Promise<boolean>
  onMicDenied: () => void
  onMicAllowed: () => void
}

export function useMobileKittyMicPtt(options: UseMobileKittyMicPttOptions) {
  const {
    kitty,
    kittyServerEnabled,
    connecting,
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

  async function beginKittyMicFromUser(): Promise<void> {
    if (!kittyServerEnabled.value || connecting.value || micDenied.value) {
      return
    }
    if (kitty.isVoiceActive.value || voiceStartInFlight.value) {
      return
    }
    voiceStartInFlight.value = true
    try {
      const ok = await ensureConnected()
      if (!ok || !isKittyMicHoldActive()) {
        return
      }
      await kitty.startVoiceInput()
      if (!isKittyMicHoldActive()) {
        kitty.stopVoiceInput()
      } else {
        onMicAllowed()
      }
    } catch {
      onMicDenied()
    } finally {
      voiceStartInFlight.value = false
    }
  }

  function endKittyMicFromUser(): void {
    pttPointerActive.value = false
    spacePttActive = false
    if (kitty.isVoiceActive.value) {
      kitty.stopVoiceInput()
    }
  }

  function onKittyMicPointerDown(ev: PointerEvent): void {
    if (ev.button !== 0) {
      return
    }
    if (!kittyServerEnabled.value || connecting.value || micDenied.value) {
      return
    }
    pttPointerActive.value = true
    const el = ev.currentTarget
    if (el instanceof HTMLElement) {
      el.setPointerCapture(ev.pointerId)
    }
    ev.preventDefault()
    void beginKittyMicFromUser()
  }

  function onKittyMicPointerUp(ev: PointerEvent): void {
    pttPointerActive.value = false
    if (kitty.isVoiceActive.value) {
      kitty.stopVoiceInput()
    }
    const el = ev.currentTarget
    if (el instanceof HTMLElement && el.hasPointerCapture(ev.pointerId)) {
      try {
        el.releasePointerCapture(ev.pointerId)
      } catch {
        /* ignore */
      }
    }
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
    if (!kittyServerEnabled.value || connecting.value || micDenied.value) {
      return
    }
    ev.preventDefault()
    if (spacePttActive) {
      return
    }
    spacePttActive = true
    void beginKittyMicFromUser()
  }

  function onKittySpacePttKeyUp(ev: KeyboardEvent): void {
    if (ev.code !== 'Space' && ev.key !== ' ') {
      return
    }
    if (!spacePttActive) {
      return
    }
    spacePttActive = false
    if (kitty.isVoiceActive.value) {
      kitty.stopVoiceInput()
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
    onKittyMicPointerDown,
    onKittyMicPointerUp,
    bindKittyMicKeyboard,
    teardownMicPtt,
  }
}
