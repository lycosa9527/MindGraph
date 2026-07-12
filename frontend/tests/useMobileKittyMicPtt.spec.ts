/**
 * Mobile Kitty PTT: warm mic on pointerdown, parallel WS connect, stop on release.
 */
import { nextTick, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMobileKittyMicPtt } from '@/composables/mobile/useMobileKittyMicPtt'

function makeFunAsr(overrides: {
  listening: { value: boolean }
  prepareMicFromUserGesture: ReturnType<typeof vi.fn>
  startListening: ReturnType<typeof vi.fn>
  stopListening: ReturnType<typeof vi.fn>
}) {
  return {
    ...overrides,
    blessFromUserActivation: vi.fn(),
  }
}

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
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn(async () => {
      listening.value = true
      return { ok: true as const, utteranceId: 'utt-1' }
    })
    const stopListening = vi.fn(() => {
      listening.value = false
    })
    const ensureConnected = vi.fn(async () => true)
    const onMicAllowed = vi.fn()
    const onMicDenied = vi.fn()
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening,
    })

    const { pttPointerActive, onKittyMicPointerDown, onKittyMicPointerUp, teardownMicPtt } =
      useMobileKittyMicPtt({
        funAsr,
        kittyServerEnabled: { value: true },
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

    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'mouse',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    expect(pttPointerActive.value).toBe(true)
    expect(prepareMicFromUserGesture).toHaveBeenCalled()
    expect(funAsr.blessFromUserActivation).toHaveBeenCalled()

    await nextTick()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    expect(ensureConnected).toHaveBeenCalled()
    expect(startListening).toHaveBeenCalled()
    expect(pttPointerActive.value).toBe(true)
    expect(onMicAllowed).toHaveBeenCalled()
    expect(stopListening).not.toHaveBeenCalled()

    const up = new PointerEvent('pointerup', {
      button: 0,
      pointerId: 1,
      pointerType: 'mouse',
    })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)
    expect(pttPointerActive.value).toBe(false)
    expect(stopListening).toHaveBeenCalled()

    teardownMicPtt()
  })

  it('blesses on touch pointerup (WebKit activation-triggering)', async () => {
    const listening = ref(false)
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn(async () => {
      listening.value = true
      return { ok: true as const, utteranceId: 'utt-1' }
    })
    const stopListening = vi.fn(() => {
      listening.value = false
    })
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening,
    })

    const { onKittyMicPointerDown, onKittyMicPointerUp, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: vi.fn(async () => true),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    expect(prepareMicFromUserGesture).toHaveBeenCalled()

    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    funAsr.blessFromUserActivation.mockClear()
    const up = new PointerEvent('pointerup', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)
    expect(funAsr.blessFromUserActivation).toHaveBeenCalled()
    expect(stopListening).toHaveBeenCalled()

    teardownMicPtt()
  })

  it('starts ASR when iOS rejects pointer capture', async () => {
    const listening = ref(false)
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn(async () => {
      listening.value = true
      return { ok: true as const, utteranceId: 'utt-1' }
    })
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening: vi.fn(() => {
        listening.value = false
      }),
    })

    const { onKittyMicPointerDown, pttPointerActive, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: vi.fn(async () => true),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn(() => {
      throw new DOMException('Invalid pointer id', 'NotFoundError')
    })
    btn.hasPointerCapture = vi.fn(() => false)

    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 7,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)

    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    expect(pttPointerActive.value).toBe(true)
    expect(prepareMicFromUserGesture).toHaveBeenCalled()
    expect(prepareMicFromUserGesture.mock.invocationCallOrder[0]).toBeLessThan(
      btn.setPointerCapture.mock.invocationCallOrder[0] ?? Number.MAX_SAFE_INTEGER
    )
    expect(startListening).toHaveBeenCalled()
    teardownMicPtt()
  })

  it('warms mic while connect is in flight and keeps the hold', async () => {
    const listening = ref(false)
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn(async () => {
      listening.value = true
      return { ok: true as const, utteranceId: 'utt-1' }
    })
    const stopListening = vi.fn()
    let resolveConnect: ((ok: boolean) => void) | undefined
    const ensureConnected = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          resolveConnect = resolve
        })
    )
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening,
    })

    const { pttPointerActive, onKittyMicPointerDown, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: false },
      ensureConnected,
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)
    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'mouse',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)

    expect(pttPointerActive.value).toBe(true)
    expect(prepareMicFromUserGesture).toHaveBeenCalled()
    expect(ensureConnected).toHaveBeenCalled()

    resolveConnect?.(true)
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    expect(startListening).toHaveBeenCalled()
    expect(pttPointerActive.value).toBe(true)

    teardownMicPtt()
  })

  it('does not start Fun-ASR when server flag is off', async () => {
    const listening = ref(false)
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn(async () => {
      listening.value = true
      return { ok: true as const, utteranceId: 'utt-1' }
    })
    const stopListening = vi.fn()
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening,
    })

    const { onKittyMicPointerDown, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: false },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: false },
      ensureConnected: vi.fn(async () => false),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    await Promise.resolve()
    expect(prepareMicFromUserGesture).not.toHaveBeenCalled()
    expect(startListening).not.toHaveBeenCalled()
    teardownMicPtt()
  })

  it('does not start listening when hold ends before connect finishes', async () => {
    const listening = ref(false)
    const prepareMicFromUserGesture = vi.fn(async () => true)
    const startListening = vi.fn()
    const stopListening = vi.fn()
    const onPttAborted = vi.fn()
    let resolveConnect: ((ok: boolean) => void) | undefined
    const ensureConnected = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          resolveConnect = resolve
        })
    )
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture,
      startListening,
      stopListening,
    })

    const { onKittyMicPointerDown, onKittyMicPointerUp, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: false },
      ensureConnected,
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
      onPttAborted,
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)

    const up = new PointerEvent('pointerup', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)

    resolveConnect?.(true)
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    expect(startListening).not.toHaveBeenCalled()
    expect(onPttAborted).toHaveBeenCalledWith('released_early')
    teardownMicPtt()
  })

  it('aborts with context_dead when startListening reports a dead capture graph', async () => {
    const listening = ref(false)
    const onPttAborted = vi.fn()
    const startListening = vi.fn(async () => ({
      ok: false as const,
      reason: 'context_dead' as const,
    }))
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture: vi.fn(async () => true),
      startListening,
      stopListening: vi.fn(),
    })

    const { onKittyMicPointerDown, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: vi.fn(async () => true),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
      onPttAborted,
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)
    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    expect(onPttAborted).toHaveBeenCalledWith('context_dead')
    expect(listening.value).toBe(false)
    teardownMicPtt()
  })

  it('stops listening when the hold ends during startListening', async () => {
    const listening = ref(false)
    let resolveStart: ((value: { ok: true; utteranceId: string }) => void) | undefined
    const startListening = vi.fn(
      () =>
        new Promise<{ ok: true; utteranceId: string }>((resolve) => {
          resolveStart = resolve
        })
    )
    const stopListening = vi.fn(() => {
      listening.value = false
    })
    const funAsr = makeFunAsr({
      listening,
      prepareMicFromUserGesture: vi.fn(async () => true),
      startListening,
      stopListening,
    })

    const { onKittyMicPointerDown, onKittyMicPointerUp, teardownMicPtt } = useMobileKittyMicPtt({
      funAsr,
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: vi.fn(async () => true),
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)
    const down = new PointerEvent('pointerdown', {
      button: 0,
      pointerId: 3,
      pointerType: 'touch',
    })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    onKittyMicPointerDown(down)
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    expect(startListening).toHaveBeenCalled()

    const up = new PointerEvent('pointerup', {
      button: 0,
      pointerId: 3,
      pointerType: 'touch',
    })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)

    resolveStart?.({ ok: true, utteranceId: 'utt-late' })
    await Promise.resolve()
    await Promise.resolve()
    expect(stopListening).toHaveBeenCalled()
    teardownMicPtt()
  })
})
