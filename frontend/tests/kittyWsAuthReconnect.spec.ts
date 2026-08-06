import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  ensureFreshSessionAfterAuthFailure,
  awaitSessionRefreshIdle,
  getSessionRefreshEpoch,
  isSessionRefreshRateLimited,
} = vi.hoisted(() => ({
  ensureFreshSessionAfterAuthFailure: vi.fn(async () => true),
  awaitSessionRefreshIdle: vi.fn(async () => undefined),
  getSessionRefreshEpoch: vi.fn(() => 0),
  isSessionRefreshRateLimited: vi.fn(() => false),
}))

vi.mock('@/utils/sessionRefresh', () => ({
  awaitSessionRefreshIdle,
  ensureFreshSessionAfterAuthFailure,
  getSessionRefreshEpoch,
  isSessionRefreshRateLimited,
}))

import { KittyConnectCloseError } from '@/composables/kitty/kittyConnectFailure'
import {
  classifyKittyConnectError,
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

describe('classifyKittyConnectError', () => {
  it('maps close codes to auth / access / scope outcomes', () => {
    expect(classifyKittyConnectError(new KittyConnectCloseError(4001, 'auth'))).toBe('auth_failed')
    expect(classifyKittyConnectError(new KittyConnectCloseError(4003, 'denied'))).toBe(
      'access_denied'
    )
    expect(classifyKittyConnectError(new KittyConnectCloseError(4403, 'scope'))).toBe('scope_denied')
    expect(classifyKittyConnectError(new KittyConnectCloseError(1006, ''))).toBe('failed')
    expect(classifyKittyConnectError(new Error('Connection superseded by a newer socket'))).toBe(
      'aborted'
    )
  })
})

describe('runKittyConnectWithAuthRecovery', () => {
  beforeEach(() => {
    ensureFreshSessionAfterAuthFailure.mockReset()
    ensureFreshSessionAfterAuthFailure.mockResolvedValue(true)
    awaitSessionRefreshIdle.mockClear()
    getSessionRefreshEpoch.mockReset()
    getSessionRefreshEpoch.mockReturnValue(0)
    isSessionRefreshRateLimited.mockReset()
    isSessionRefreshRateLimited.mockReturnValue(false)
  })

  function baseDeps(overrides: Record<string, unknown> = {}) {
    const gate = createKittyWsAuthReconnectGate()
    return {
      isHardStopped: gate.isHardStopped,
      markHardStopped: gate.markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired: vi.fn(),
      connectOnce: vi.fn(async () => 'connected' as const),
      canAttemptAuthRefresh: gate.canAttemptAuthRefresh,
      markAuthRefreshConsumed: gate.markAuthRefreshConsumed,
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

  it('does not refresh on transport failure', async () => {
    const deps = baseDeps({
      connectOnce: vi.fn(async () => 'failed' as const),
    })
    const ok = await runKittyConnectWithAuthRecovery(deps)
    expect(ok).toBe(false)
    expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
    expect(deps.onSessionExpired).not.toHaveBeenCalled()
  })

  it('hard-stops access/scope denials without refresh or session expiry', async () => {
    for (const result of ['access_denied', 'scope_denied'] as const) {
      const markHardStopped = vi.fn()
      const onSessionExpired = vi.fn()
      const ok = await runKittyConnectWithAuthRecovery({
        isHardStopped: () => false,
        markHardStopped,
        hasAuthenticatedUser: () => true,
        onSessionExpired,
        connectOnce: vi.fn(async () => result),
      })
      expect(ok).toBe(false)
      expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
      expect(markHardStopped).toHaveBeenCalled()
      expect(onSessionExpired).not.toHaveBeenCalled()
      ensureFreshSessionAfterAuthFailure.mockClear()
    }
  })

  it('refreshes only on auth_failed then retries connect', async () => {
    getSessionRefreshEpoch.mockReturnValue(3)
    const connectOnce = vi
      .fn()
      .mockResolvedValueOnce('auth_failed')
      .mockResolvedValueOnce('connected')
    const deps = baseDeps({ connectOnce })
    const ok = await runKittyConnectWithAuthRecovery(deps)
    expect(ok).toBe(true)
    expect(ensureFreshSessionAfterAuthFailure).toHaveBeenCalledTimes(1)
    expect(ensureFreshSessionAfterAuthFailure).toHaveBeenCalledWith(3)
    expect(connectOnce).toHaveBeenCalledTimes(2)
  })

  it('does not refresh again when auth budget is already consumed', async () => {
    const gate = createKittyWsAuthReconnectGate()
    gate.markAuthRefreshConsumed()
    const connectOnce = vi.fn(async () => 'auth_failed' as const)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: gate.isHardStopped,
      markHardStopped: gate.markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired: vi.fn(),
      canAttemptAuthRefresh: gate.canAttemptAuthRefresh,
      markAuthRefreshConsumed: gate.markAuthRefreshConsumed,
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(connectOnce).toHaveBeenCalledTimes(1)
    expect(ensureFreshSessionAfterAuthFailure).not.toHaveBeenCalled()
  })

  it('hard-stops without session expired when refresh is rate-limited', async () => {
    ensureFreshSessionAfterAuthFailure.mockResolvedValue(false)
    isSessionRefreshRateLimited.mockReturnValue(true)
    const markHardStopped = vi.fn()
    const onSessionExpired = vi.fn()
    const gate = createKittyWsAuthReconnectGate()
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired,
      canAttemptAuthRefresh: gate.canAttemptAuthRefresh,
      markAuthRefreshConsumed: gate.markAuthRefreshConsumed,
      connectOnce: vi.fn(async () => 'auth_failed' as const),
    })
    expect(ok).toBe(false)
    expect(markHardStopped).toHaveBeenCalledTimes(1)
    expect(onSessionExpired).not.toHaveBeenCalled()
  })

  it('hard-stops and expires session when auth refresh fails', async () => {
    ensureFreshSessionAfterAuthFailure.mockResolvedValue(false)
    const markHardStopped = vi.fn()
    const onSessionExpired = vi.fn()
    const gate = createKittyWsAuthReconnectGate()
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired,
      canAttemptAuthRefresh: gate.canAttemptAuthRefresh,
      markAuthRefreshConsumed: gate.markAuthRefreshConsumed,
      connectOnce: vi.fn(async () => 'auth_failed' as const),
    })
    expect(ok).toBe(false)
    expect(markHardStopped).toHaveBeenCalledTimes(1)
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })

  it('hard-stops when refresh ok but retry is policy-denied', async () => {
    const connectOnce = vi
      .fn()
      .mockResolvedValueOnce('auth_failed')
      .mockResolvedValueOnce('scope_denied')
    const markHardStopped = vi.fn()
    const onSessionExpired = vi.fn()
    const gate = createKittyWsAuthReconnectGate()
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      onSessionExpired,
      canAttemptAuthRefresh: gate.canAttemptAuthRefresh,
      markAuthRefreshConsumed: gate.markAuthRefreshConsumed,
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(ensureFreshSessionAfterAuthFailure).toHaveBeenCalledTimes(1)
    expect(connectOnce).toHaveBeenCalledTimes(2)
    expect(markHardStopped).toHaveBeenCalledTimes(1)
    expect(onSessionExpired).not.toHaveBeenCalled()
  })
})

describe('createKittyWsAuthReconnectGate', () => {
  it('latches hard-stop and auth-refresh budget until reset', () => {
    const gate = createKittyWsAuthReconnectGate()
    expect(gate.isHardStopped()).toBe(false)
    expect(gate.canAttemptAuthRefresh()).toBe(true)
    gate.markHardStopped()
    gate.markAuthRefreshConsumed()
    expect(gate.isHardStopped()).toBe(true)
    expect(gate.canAttemptAuthRefresh()).toBe(false)
    gate.reset()
    expect(gate.isHardStopped()).toBe(false)
    expect(gate.canAttemptAuthRefresh()).toBe(true)
  })
})
