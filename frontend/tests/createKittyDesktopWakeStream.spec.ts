import { afterEach, describe, expect, it, vi } from 'vitest'

import { createKittyDesktopWakeStream } from '@/composables/kitty/createKittyDesktopWakeStream'

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

class FakeEventSource {
  static instances: FakeEventSource[] = []
  static fireErrorOnClose = false

  readonly url: string
  readonly fireErrorOnClose: boolean
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    this.fireErrorOnClose = FakeEventSource.fireErrorOnClose
    FakeEventSource.instances.push(this)
  }

  close(): void {
    if (this.closed) {
      return
    }
    this.closed = true
    if (this.fireErrorOnClose) {
      this.onerror?.(new Event('error'))
    }
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
    FakeEventSource.fireErrorOnClose = false
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

  it('does not invoke onClose when the caller stops the stream', () => {
    vi.stubGlobal('EventSource', FakeEventSource)

    const onClose = vi.fn()
    const stop = createKittyDesktopWakeStream({
      onMobileActive: vi.fn(),
      onClose,
    })

    stop()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('invokes onClose once on unexpected drop even if close() re-fires error', () => {
    FakeEventSource.fireErrorOnClose = true
    vi.stubGlobal('EventSource', FakeEventSource)

    const onClose = vi.fn()
    const stop = createKittyDesktopWakeStream({
      shouldReconnect: () => false,
      onMobileActive: vi.fn(),
      onClose,
    })

    FakeEventSource.instances[0]?.triggerError()
    expect(onClose).toHaveBeenCalledTimes(1)

    stop()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not recurse when onClose tears the stream down', () => {
    vi.stubGlobal('EventSource', FakeEventSource)

    let stop: (() => void) | null = null
    let depth = 0
    let maxDepth = 0
    const onClose = vi.fn(() => {
      depth += 1
      maxDepth = Math.max(maxDepth, depth)
      stop?.()
      depth -= 1
    })
    stop = createKittyDesktopWakeStream({
      shouldReconnect: () => false,
      onMobileActive: vi.fn(),
      onClose,
    })

    FakeEventSource.instances[0]?.triggerError()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(maxDepth).toBe(1)
  })
})
