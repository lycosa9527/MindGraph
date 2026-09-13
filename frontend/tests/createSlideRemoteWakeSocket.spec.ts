import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  SLIDE_REMOTE_COMMAND_PENDING_TYPE,
  SLIDE_REMOTE_WAKE_WS_PATH,
  createSlideRemoteWakeSocket,
} from '@/composables/mindMap/createSlideRemoteWakeSocket'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  readonly url: string
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  sent: string[] = []

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(data: string): void {
    this.sent.push(data)
  }

  close(): void {
    this.onclose?.(new CloseEvent('close'))
  }
}

describe('createSlideRemoteWakeSocket', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    FakeWebSocket.instances = []
  })

  it('opens the slides-remote WebSocket path', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const stop = createSlideRemoteWakeSocket({
      onCommandPending: vi.fn(),
    })
    expect(FakeWebSocket.instances[0]?.url).toContain(SLIDE_REMOTE_WAKE_WS_PATH)
    stop()
  })

  it('notifies on slides_command_pending and replies to ping', () => {
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const onCommandPending = vi.fn()
    const stop = createSlideRemoteWakeSocket({ onCommandPending })
    const socket = FakeWebSocket.instances[0]
    socket?.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'ping' }) }))
    socket?.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify({ type: SLIDE_REMOTE_COMMAND_PENDING_TYPE }),
      })
    )
    expect(socket?.sent).toEqual([JSON.stringify({ type: 'pong' })])
    expect(onCommandPending).toHaveBeenCalledOnce()
    stop()
  })

  it('does not schedule reconnect when shouldReconnect returns false', () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const shouldReconnect = vi.fn(() => false)
    const stop = createSlideRemoteWakeSocket({
      shouldReconnect,
      onCommandPending: vi.fn(),
    })
    FakeWebSocket.instances[0]?.close()
    expect(shouldReconnect).toHaveBeenCalled()
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
    stop()
  })

  it('reconnects with backoff when shouldReconnect stays true', () => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const stop = createSlideRemoteWakeSocket({
      shouldReconnect: () => true,
      onCommandPending: vi.fn(),
    })
    FakeWebSocket.instances[0]?.close()
    vi.advanceTimersByTime(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)
    stop()
  })
})
