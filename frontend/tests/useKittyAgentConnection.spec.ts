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
})
