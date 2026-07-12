/**
 * End-to-end PTT path under an iOS Safari Web Audio policy simulator.
 *
 * Real iPhone Safari cannot run in CI. This suite models the constraints that
 * caused production failures:
 * - AudioContext starts suspended
 * - resume() only unlocks inside a user-gesture call stack
 * - getUserMedia can succeed (orange LED) while context stays suspended
 * - ScriptProcessor emits samples only when context.state === 'running'
 *
 * Pass criteria: hold → ws asr_start + asr_audio frames with ctx running.
 */
import { nextTick, shallowRef } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/stores/kittySession', () => ({
  useKittySessionStore: () => ({
    setAsrListening: vi.fn(),
  }),
}))

import { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { useMobileKittyMicPtt } from '@/composables/mobile/useMobileKittyMicPtt'

type FakeState = 'suspended' | 'running' | 'closed'

/** Tracks whether code is executing inside a simulated pointerdown stack. */
let gestureStackDepth = 0

function runInUserGesture<T>(fn: () => T): T {
  gestureStackDepth += 1
  try {
    return fn()
  } finally {
    gestureStackDepth -= 1
  }
}

function isInUserGesture(): boolean {
  return gestureStackDepth > 0
}

class FakeAudioBuffer {
  constructor(
    readonly numberOfChannels: number,
    readonly length: number,
    readonly sampleRate: number
  ) {}
}

class FakeBufferSource {
  buffer: FakeAudioBuffer | null = null
  connect(): void {
    /* no-op */
  }
  start(): void {
    /* no-op */
  }
}

class FakeGainNode {
  gain = { value: 1 }
  connect(): void {
    /* no-op */
  }
  disconnect(): void {
    /* no-op */
  }
}

class FakeMediaStreamSource {
  connect(): void {
    /* no-op */
  }
  disconnect(): void {
    /* no-op */
  }
}

class FakeScriptProcessor {
  onaudioprocess:
    | ((event: { inputBuffer: { getChannelData: (ch: number) => Float32Array } }) => void)
    | null = null

  connect(): void {
    /* no-op */
  }

  disconnect(): void {
    /* no-op */
  }

  /** Test helper — only delivers samples when AudioContext is running (iOS). */
  emitSamples(ctx: FakeAudioContext, samples: Float32Array): void {
    if (ctx.state !== 'running' || !this.onaudioprocess) {
      return
    }
    this.onaudioprocess({
      inputBuffer: {
        getChannelData: () => samples,
      },
    })
  }
}

class FakeAudioContext {
  state: FakeState = 'suspended'
  sampleRate = 48000
  destination = {}
  lastScriptProcessor: FakeScriptProcessor | null = null

  createBuffer(channels: number, length: number, rate: number): FakeAudioBuffer {
    return new FakeAudioBuffer(channels, length, rate)
  }

  createBufferSource(): FakeBufferSource {
    return new FakeBufferSource()
  }

  createGain(): FakeGainNode {
    return new FakeGainNode()
  }

  createScriptProcessor(): FakeScriptProcessor {
    const node = new FakeScriptProcessor()
    this.lastScriptProcessor = node
    return node
  }

  createMediaStreamSource(_stream: MediaStream): FakeMediaStreamSource {
    return new FakeMediaStreamSource()
  }

  /**
   * iOS Safari: resume() only unlocks when called from a user-gesture stack.
   * Calling it after an await (microtask) leaves the context suspended.
   */
  resume(): Promise<void> {
    if (this.state === 'closed') {
      return Promise.reject(new Error('InvalidStateError'))
    }
    if (isInUserGesture()) {
      this.state = 'running'
    }
    return Promise.resolve()
  }

  close(): Promise<void> {
    this.state = 'closed'
    return Promise.resolve()
  }
}

function makeOpenWs(): {
  ws: WebSocket
  sent: Array<Record<string, unknown>>
} {
  const sent: Array<Record<string, unknown>> = []
  const ws = {
    readyState: 1, // WebSocket.OPEN
    send: (raw: string) => {
      sent.push(JSON.parse(raw) as Record<string, unknown>)
    },
  } as unknown as WebSocket
  return { ws, sent }
}

function installIosSafariAudioMocks(): {
  getUserMedia: ReturnType<typeof vi.fn>
  micLedOn: { value: boolean }
  contexts: FakeAudioContext[]
  track: { enabled: boolean; stop: ReturnType<typeof vi.fn> }
} {
  const contexts: FakeAudioContext[] = []
  const micLedOn = { value: false }
  const track = {
    enabled: true,
    stop: vi.fn(),
  }

  class FakeAudioContextCtor extends FakeAudioContext {
    constructor() {
      super()
      contexts.push(this)
    }
  }

  Object.defineProperty(window, 'AudioContext', {
    configurable: true,
    writable: true,
    value: FakeAudioContextCtor,
  })
  Object.defineProperty(window, 'webkitAudioContext', {
    configurable: true,
    writable: true,
    value: FakeAudioContextCtor,
  })

  const stream = {
    getTracks: () => [track],
    getAudioTracks: () => [track],
  } as unknown as MediaStream

  const getUserMedia = vi.fn(async () => {
    micLedOn.value = true
    return stream
  })

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  })

  return { getUserMedia, micLedOn, contexts, track }
}

describe('iOS Safari PTT end-to-end (Web Audio policy simulator)', () => {
  beforeEach(() => {
    gestureStackDepth = 0
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('proves the broken pattern: await before resume → LED on, zero PCM', async () => {
    const { micLedOn, contexts } = installIosSafariAudioMocks()

    // Simulate old buggy flow: getUserMedia OK, then await, then resume outside gesture.
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    expect(micLedOn.value).toBe(true)
    expect(stream).toBeTruthy()

    await Promise.resolve() // user activation expired (iOS)

    const ctx = new window.AudioContext() as unknown as FakeAudioContext
    expect(contexts.length).toBeGreaterThan(0)
    await ctx.resume() // NOT in gesture stack
    expect(ctx.state).toBe('suspended')

    const processor = ctx.createScriptProcessor()
    let pcmCallbacks = 0
    processor.onaudioprocess = () => {
      pcmCallbacks += 1
    }
    processor.emitSamples(ctx, new Float32Array(128).fill(0.2))
    expect(pcmCallbacks).toBe(0)
  })

  it('hold-to-talk sends asr_start + asr_audio when blessed in pointerdown', async () => {
    const { micLedOn, contexts, getUserMedia } = installIosSafariAudioMocks()
    const { ws, sent } = makeOpenWs()
    const wsRef = shallowRef<WebSocket | null>(ws)
    const onMicDenied = vi.fn()
    const onError = vi.fn()

    const funAsr = useKittyFunAsrMic({
      ws: wsRef,
      stopPlayback: vi.fn(),
      ensureConnected: async () => true,
      onError,
    })

    const {
      pttPointerActive,
      onKittyMicPointerDown,
      onKittyMicPointerUp,
      teardownMicPtt,
    } = useMobileKittyMicPtt({
      funAsr: {
        listening: funAsr.listening,
        prepareMicFromUserGesture: funAsr.prepareMicFromUserGesture,
        startListening: funAsr.startListening,
        stopListening: funAsr.stopListening,
      },
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: async () => true,
      onMicDenied,
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const down = new PointerEvent('pointerdown', { button: 0, pointerId: 1 })
    Object.defineProperty(down, 'currentTarget', { value: btn })

    runInUserGesture(() => {
      onKittyMicPointerDown(down)
    })

    expect(pttPointerActive.value).toBe(true)
    expect(getUserMedia).toHaveBeenCalled()

    for (let i = 0; i < 10; i += 1) {
      await Promise.resolve()
    }
    await nextTick()

    expect(onMicDenied).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
    expect(micLedOn.value).toBe(true)
    expect(funAsr.listening.value).toBe(true)
    expect(contexts.length).toBeGreaterThan(0)
    expect(contexts[0]?.state).toBe('running')
    expect(funAsr.debugCtxState.value).toBe('running')
    expect(sent.map((m) => m.type)).toContain('asr_start')

    const processor = contexts[0]?.lastScriptProcessor
    expect(processor).toBeTruthy()
    const chunk = new Float32Array(4800)
    for (let i = 0; i < chunk.length; i += 1) {
      chunk[i] = Math.sin(i / 10) * 0.4
    }
    processor?.emitSamples(contexts[0] as FakeAudioContext, chunk)
    processor?.emitSamples(contexts[0] as FakeAudioContext, chunk)

    expect(funAsr.debugFramesSent.value).toBeGreaterThan(0)
    expect(sent.map((m) => m.type)).toContain('asr_audio')

    const up = new PointerEvent('pointerup', { button: 0, pointerId: 1 })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    onKittyMicPointerUp(up)

    expect(funAsr.listening.value).toBe(false)
    expect(sent.map((m) => m.type)).toContain('asr_stop')

    teardownMicPtt()
    funAsr.teardownWarmMic()
  })

  it('second hold reuses warm session without recreating AudioContext', async () => {
    installIosSafariAudioMocks()
    const { ws } = makeOpenWs()
    const wsRef = shallowRef<WebSocket | null>(ws)

    const funAsr = useKittyFunAsrMic({
      ws: wsRef,
      stopPlayback: vi.fn(),
      ensureConnected: async () => true,
    })

    const ptt = useMobileKittyMicPtt({
      funAsr: {
        listening: funAsr.listening,
        prepareMicFromUserGesture: funAsr.prepareMicFromUserGesture,
        startListening: funAsr.startListening,
        stopListening: funAsr.stopListening,
      },
      kittyServerEnabled: { value: true },
      micDenied: { value: false },
      showKeyboard: { value: false },
      connected: { value: true },
      ensureConnected: async () => true,
      onMicDenied: vi.fn(),
      onMicAllowed: vi.fn(),
    })

    const btn = document.createElement('button')
    btn.setPointerCapture = vi.fn()
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const press = async (pointerId: number) => {
      const down = new PointerEvent('pointerdown', { button: 0, pointerId })
      Object.defineProperty(down, 'currentTarget', { value: btn })
      runInUserGesture(() => {
        ptt.onKittyMicPointerDown(down)
      })
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
      const up = new PointerEvent('pointerup', { button: 0, pointerId })
      Object.defineProperty(up, 'currentTarget', { value: btn })
      ptt.onKittyMicPointerUp(up)
    }

    await press(1)
    const ctxAfterFirst = funAsr.debugCtxState.value
    expect(ctxAfterFirst).toBe('running')

    await press(2)
    expect(funAsr.debugCtxState.value).toBe('running')

    ptt.teardownMicPtt()
    funAsr.teardownWarmMic()
  })

  it('does not send asr_audio if hold ends before listening starts', async () => {
    installIosSafariAudioMocks()
    const { ws, sent } = makeOpenWs()
    const wsRef = shallowRef<WebSocket | null>(ws)

    let resolveConnect: ((ok: boolean) => void) | undefined
    const ensureConnected = () =>
      new Promise<boolean>((resolve) => {
        resolveConnect = resolve
      })

    const funAsr = useKittyFunAsrMic({
      ws: wsRef,
      stopPlayback: vi.fn(),
      ensureConnected,
    })

    const ptt = useMobileKittyMicPtt({
      funAsr: {
        listening: funAsr.listening,
        prepareMicFromUserGesture: funAsr.prepareMicFromUserGesture,
        startListening: funAsr.startListening,
        stopListening: funAsr.stopListening,
      },
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
    btn.releasePointerCapture = vi.fn()
    btn.hasPointerCapture = vi.fn(() => true)

    const down = new PointerEvent('pointerdown', { button: 0, pointerId: 1 })
    Object.defineProperty(down, 'currentTarget', { value: btn })
    runInUserGesture(() => {
      ptt.onKittyMicPointerDown(down)
    })

    const up = new PointerEvent('pointerup', { button: 0, pointerId: 1 })
    Object.defineProperty(up, 'currentTarget', { value: btn })
    ptt.onKittyMicPointerUp(up)

    resolveConnect?.(true)
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    expect(funAsr.listening.value).toBe(false)
    expect(sent.some((m) => m.type === 'asr_start')).toBe(false)

    ptt.teardownMicPtt()
    funAsr.teardownWarmMic()
  })
})
