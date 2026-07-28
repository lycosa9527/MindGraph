import { afterEach, describe, expect, it, vi } from 'vitest'

import { createKittyDesktopWakeStream } from '@/composables/kitty/createKittyDesktopWakeStream'

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

class FakeEventSource {
  static instances: FakeEventSource[] = []

  readonly url: string
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  close(): void {
    this.closed = true
  }

  triggerError(): void {
    this.onerror?.(new Event('error'))
  }
}

describe('createKittyDesktopWakeStream', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    FakeEventSource.instances = []
  })

  it('does not schedule reconnect when shouldReconnect returns false', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource)

    const shouldReconnect = vi.fn(() => false)
    const stop = createKittyDesktopWakeStream({
      shouldReconnect,
      onMobileActive: vi.fn(),
    })

    expect(FakeEventSource.instances).toHaveLength(1)
    FakeEventSource.instances[0]?.triggerError()
    expect(shouldReconnect).toHaveBeenCalled()

    vi.advanceTimersByTime(60_000)
    expect(FakeEventSource.instances).toHaveLength(1)

    stop()
  })

  it('reconnects with backoff when shouldReconnect stays true', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource)

    const stop = createKittyDesktopWakeStream({
      shouldReconnect: () => true,
      onMobileActive: vi.fn(),
    })

    expect(FakeEventSource.instances).toHaveLength(1)
    FakeEventSource.instances[0]?.triggerError()

    vi.advanceTimersByTime(1000)
    expect(FakeEventSource.instances).toHaveLength(2)

    stop()
  })

  it('reconnects by default when shouldReconnect is omitted', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource)

    const stop = createKittyDesktopWakeStream({
      onMobileActive: vi.fn(),
    })

    FakeEventSource.instances[0]?.triggerError()
    vi.advanceTimersByTime(1000)
    expect(FakeEventSource.instances).toHaveLength(2)

    stop()
  })
})
