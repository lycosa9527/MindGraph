import { afterEach, describe, expect, it, vi } from 'vitest'

import { useKittyAgent } from '@/composables/kitty/useKittyAgent'

vi.mock('@/stores/kittySession', () => ({
  useKittySessionStore: () => ({
    hubScopeRevision: null,
    setHubScopeRevision: vi.fn(),
    setOwnsKittySession: vi.fn(),
  }),
}))

class SuspendedAudioContext {
  static instances: SuspendedAudioContext[] = []

  state: AudioContextState = 'suspended'
  resume = vi.fn(() => new Promise<void>(() => undefined))
  suspend = vi.fn(async () => undefined)
  close = vi.fn(async () => {
    this.state = 'closed'
  })

  constructor() {
    SuspendedAudioContext.instances.push(this)
  }
}

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly url: string
  readyState = FakeWebSocket.CONNECTING
  sent: Array<Record<string, unknown>> = []
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(raw: string): void {
    this.sent.push(JSON.parse(raw) as Record<string, unknown>)
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  receive(payload: Record<string, unknown>): void {
    this.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify(payload),
      })
    )
  }
}

describe('useKittyAgent connection', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    SuspendedAudioContext.instances = []
    FakeWebSocket.instances = []
  })

  it('opens Kitty WebSocket without waiting for suspended Web Audio', async () => {
    vi.stubGlobal('AudioContext', SuspendedAudioContext)
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const agent = useKittyAgent({ kittyClientLane: 'mobile' })
    const connecting = agent.startConversation('mobile-scope', {
      diagram_type: 'circle_map',
      active_panel: 'none',
    })

    expect(SuspendedAudioContext.instances).toHaveLength(1)
    expect(SuspendedAudioContext.instances[0]?.resume).not.toHaveBeenCalled()
    expect(FakeWebSocket.instances).toHaveLength(1)

    const socket = FakeWebSocket.instances[0]
    expect(socket?.url).toContain('/ws/kitty/mobile-scope')
    socket?.open()
    expect(socket?.sent[0]).toMatchObject({
      type: 'start',
      client_mode: 'text',
      client_lane: 'mobile',
    })

    socket?.receive({ type: 'connected', session_id: 'voice-session' })
    await connecting

    expect(agent.isConnected.value).toBe(true)
    expect(agent.isActive.value).toBe(true)
    agent.destroy()
  })

  it('ignores a stale close event after a scope reconnect', async () => {
    vi.stubGlobal('AudioContext', SuspendedAudioContext)
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const agent = useKittyAgent({ kittyClientLane: 'mobile' })
    const firstConnecting = agent.startConversation('old-scope')
    const oldSocket = FakeWebSocket.instances[0]
    oldSocket?.open()
    oldSocket?.receive({ type: 'connected', session_id: 'old-session' })
    await firstConnecting

    const queuedOldClose = oldSocket?.onclose
    await agent.stopConversation()

    const secondConnecting = agent.startConversation('new-scope')
    const newSocket = FakeWebSocket.instances[1]
    newSocket?.open()
    newSocket?.receive({ type: 'connected', session_id: 'new-session' })
    await secondConnecting

    queuedOldClose?.(new CloseEvent('close', { code: 1000, reason: 'old scope closed' }))

    expect(agent.diagramSessionId.value).toBe('new-scope')
    expect(agent.isConnected.value).toBe(true)
    expect(agent.isActive.value).toBe(true)
    agent.destroy()
  })

  it('cancels a pending handshake immediately on stopConversation', async () => {
    vi.stubGlobal('AudioContext', SuspendedAudioContext)
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const agent = useKittyAgent({ kittyClientLane: 'mobile' })
    const connecting = agent.startConversation('mobile-scope')
    expect(FakeWebSocket.instances).toHaveLength(1)
    FakeWebSocket.instances[0]?.open()

    const stopped = agent.stopConversation()
    await expect(connecting).rejects.toThrow(/stopped|Connection|cancel/i)
    await stopped
    expect(agent.isConnected.value).toBe(false)
    expect(agent.isActive.value).toBe(false)
    agent.destroy()
  })

  it('rejects a superseded queued start when a newer scope wins', async () => {
    vi.stubGlobal('AudioContext', SuspendedAudioContext)
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const agent = useKittyAgent({ kittyClientLane: 'mobile' })
    const first = agent.startConversation('scope-a')
    await Promise.resolve()
    expect(FakeWebSocket.instances.length).toBeGreaterThanOrEqual(1)
    const firstSocket = FakeWebSocket.instances[0]
    const second = agent.startConversation('scope-b')

    // Complete the first handshake so the queued second start can run; the
    // older waiter must still settle without hanging on the 10s connect timer.
    firstSocket?.open()
    firstSocket?.receive({ type: 'connected', session_id: 'session-a' })
    await expect(first).resolves.toBeUndefined()

    await Promise.resolve()
    const secondSocket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]
    expect(secondSocket).not.toBe(firstSocket)
    secondSocket?.open()
    secondSocket?.receive({ type: 'connected', session_id: 'session-b' })
    await second
    expect(agent.diagramSessionId.value).toBe('scope-b')
    expect(agent.isConnected.value).toBe(true)
    agent.destroy()
  })

  it('sendTextMessage returns false when the socket is not open', async () => {
    vi.stubGlobal('AudioContext', SuspendedAudioContext)
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const agent = useKittyAgent({ kittyClientLane: 'mobile' })
    expect(agent.sendTextMessage('hello')).toBe(false)

    const connecting = agent.startConversation('mobile-scope')
    const socket = FakeWebSocket.instances[0]
    socket?.open()
    socket?.receive({ type: 'connected', session_id: 'voice-session' })
    await connecting

    expect(agent.sendTextMessage('hello')).toBe(true)
    expect(socket?.sent.some((msg) => msg.type === 'text' || msg.type === 'user_text')).toBe(true)
    agent.destroy()
  })
})
