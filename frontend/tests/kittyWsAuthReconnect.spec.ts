import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  ensureFreshSessionAfterAuthFailure,
  awaitSessionRefreshIdle,
  getSessionRefreshEpoch,
} = vi.hoisted(() => ({
  ensureFreshSessionAfterAuthFailure: vi.fn(async () => true),
  awaitSessionRefreshIdle: vi.fn(async () => undefined),
  getSessionRefreshEpoch: vi.fn(() => 0),
}))

vi.mock('@/utils/sessionRefresh', () => ({
  awaitSessionRefreshIdle,
  ensureFreshSessionAfterAuthFailure,
  getSessionRefreshEpoch,
}))

import {
  createKittyWsAuthReconnectGate,
  isKittyConnectAbortError,
  runKittyConnectWithAuthRecovery,
} from '@/composables/kitty/kittyWsAuthReconnect'

describe('isKittyConnectAbortError', () => {
  it('detects superseded / stop / cleanup messages', () => {
    expect(isKittyConnectAbortError(new Error('Connection superseded by a newer socket'))).toBe(
      true
    )
    expect(isKittyConnectAbortError(new Error('Conversation stopped'))).toBe(true)
    expect(isKittyConnectAbortError(new Error('Cleanup started during connection'))).toBe(true)
    expect(isKittyConnectAbortError(new Error('WebSocket connection failed'))).toBe(false)
  })
})

describe('runKittyConnectWithAuthRecovery', () => {
  beforeEach(() => {
    ensureFreshSessionAfterAuthFailure.mockReset()
    ensureFreshSessionAfterAuthFailure.mockResolvedValue(true)
    awaitSessionRefreshIdle.mockClear()
    getSessionRefreshEpoch.mockReset()
    getSessionRefreshEpoch.mockReturnValue(0)
  })

  function baseDeps(overrides: Record<string, unknown> = {}) {
    const gate = createKittyWsAuthReconnectGate()
    return {
      isHardStopped: gate.isHardStopped,
      markHardStopped: gate.markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired: vi.fn(),
      connectOnce: vi.fn(async () => 'connected' as const),
      ...overrides,
    }
  }

  it('returns true on first successful connect without stampede helper', async () => {
    const deps = baseDeps()
    const ok = await runKittyConnectWithAuthRecovery(deps)
    expect(ok).toBe(true)
    expect(deps.connectOnce).toHaveBeenCalledTimes(1)
    expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
  })

  it('does not refresh when the first attempt is aborted', async () => {
    const deps = baseDeps({
      connectOnce: vi.fn(async () => 'aborted' as const),
    })
    const ok = await runKittyConnectWithAuthRecovery(deps)
    expect(ok).toBe(false)
    expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
    expect(deps.connectOnce).toHaveBeenCalledTimes(1)
  })

  it('uses stampede helper once then retries connect after failure', async () => {
    getSessionRefreshEpoch.mockReturnValue(3)
    const connectOnce = vi
      .fn()
      .mockResolvedValueOnce('failed')
      .mockResolvedValueOnce('connected')
    const deps = baseDeps({ connectOnce })
    const ok = await runKittyConnectWithAuthRecovery(deps)
    expect(ok).toBe(true)
    expect(ensureFreshSessionAfterAuthFailure).toHaveBeenCalledTimes(1)
    expect(ensureFreshSessionAfterAuthFailure).toHaveBeenCalledWith(3)
    expect(connectOnce).toHaveBeenCalledTimes(2)
  })

  it('hard-stops when stampede helper returns false', async () => {
    ensureFreshSessionAfterAuthFailure.mockResolvedValue(false)
    const markHardStopped = vi.fn()
    const onSessionExpired = vi.fn()
    const connectOnce = vi.fn(async () => 'failed' as const)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired,
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(connectOnce).toHaveBeenCalledTimes(1)
    expect(markHardStopped).toHaveBeenCalledTimes(1)
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })

  it('does not connect when already hard-stopped', async () => {
    const connectOnce = vi.fn(async () => 'connected' as const)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => true,
      markHardStopped: vi.fn(),
      hasAuthenticatedUser: () => true,
      onSessionExpired: vi.fn(),
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(connectOnce).not.toHaveBeenCalled()
    expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
  })
})

describe('createKittyWsAuthReconnectGate', () => {
  it('latches hard-stop until reset', () => {
    const gate = createKittyWsAuthReconnectGate()
    expect(gate.isHardStopped()).toBe(false)
    gate.markHardStopped()
    expect(gate.isHardStopped()).toBe(true)
    gate.reset()
    expect(gate.isHardStopped()).toBe(false)
  })
})
