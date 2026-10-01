import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  COLLAB_SOCKET_DEAD_AFTER_MS,
  COLLAB_SOCKET_PING_AFTER_MS,
  createCollabSocketHeartbeat,
} from '@/composables/mindmate/mindmateCollabHeartbeat'

describe('createCollabSocketHeartbeat', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('asks for a pong while the socket is quiet, then reopens when none arrives', () => {
    vi.useFakeTimers()
    const sendPing = vi.fn(() => true)
    const reopen = vi.fn()
    const beat = createCollabSocketHeartbeat({
      sendPing,
      reopen,
      isActive: () => true,
    })
    beat.start()
    vi.advanceTimersByTime(COLLAB_SOCKET_PING_AFTER_MS)
    expect(sendPing).toHaveBeenCalled()
    expect(reopen).not.toHaveBeenCalled()
    vi.advanceTimersByTime(COLLAB_SOCKET_DEAD_AFTER_MS - COLLAB_SOCKET_PING_AFTER_MS)
    expect(reopen).toHaveBeenCalledOnce()
    beat.stop()
  })

  it('treats an inbound frame as life and does not reopen', () => {
    vi.useFakeTimers()
    const reopen = vi.fn()
    const beat = createCollabSocketHeartbeat({
      sendPing: () => true,
      reopen,
      isActive: () => true,
    })
    beat.start()
    vi.advanceTimersByTime(COLLAB_SOCKET_PING_AFTER_MS)
    beat.noteInbound()
    vi.advanceTimersByTime(COLLAB_SOCKET_DEAD_AFTER_MS - 1000)
    expect(reopen).not.toHaveBeenCalled()
    beat.stop()
  })
})
