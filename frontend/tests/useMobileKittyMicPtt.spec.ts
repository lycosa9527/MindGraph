/**
 * Mobile Kitty PTT drives Fun-ASR start/stop (not legacy Omni voice).
 */
import { nextTick, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMobileKittyMicPtt } from '@/composables/mobile/useMobileKittyMicPtt'

describe('useMobileKittyMicPtt', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts Fun-ASR on pointer hold and stops on release', async () => {
    const listening = ref(false)
    const startListening = vi.fn(async () => {
      listening.value = true
    })
    const stopListening = vi.fn(() => {
      listening.value = false
    })
    const ensureConnected = vi.fn(async () => true)
    const onMicAllowed = vi.fn()
    const onMicDenied = vi.fn()

    const {
      pttPointerActive,
      onKittyMicPointerDown,
      onKittyMicPointerUp,
      teardownMicPtt,
    } = useMobileKittyMicPtt({
      funAsr: { listening, startListening, stopListening },
      kittyServerEnabled: { value: true },
      connecting: { value: false },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected,
      onMicDenied,
      onMicAllowed,
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const down = new PointerEvent('pointerdown', { button: 0, pointerId: 1 })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    expect(pttPointerActive.value).toBe(true)

    await nextTick()
    await Promise.resolve()
    expect(ensureConnected).toHaveBeenCalled()
    expect(startListening).toHaveBeenCalled()
    expect(onMicAllowed).toHaveBeenCalled()
    expect(stopListening).not.toHaveBeenCalled()

    const up = new PointerEvent('pointerup', { button: 0, pointerId: 1 })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)
    expect(pttPointerActive.value).toBe(false)
    expect(stopListening).toHaveBeenCalled()

    teardownMicPtt()
  })

  it('does not start Fun-ASR when server flag is off', async () => {
    const listening = ref(false)
    const startListening = vi.fn(async () => {
      listening.value = true
    })
    const stopListening = vi.fn()

    const { onKittyMicPointerDown, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr: { listening, startListening, stopListening },
      kittyServerEnabled: { value: false },
      connecting: { value: false },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: false },
      ensureConnected: vi.fn(async () => false),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    const down = new PointerEvent('pointerdown', { button: 0, pointerId: 1 })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    await Promise.resolve()
    expect(startListening).not.toHaveBeenCalled()
    teardownMicPtt()
  })
})
