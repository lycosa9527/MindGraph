import { describe, expect, it, vi } from 'vitest'

import {
  createKittyWsAuthReconnectGate,
  recoverKittyWsAuthOrHardStop,
  runKittyConnectWithAuthRecovery,
} from '@/composables/kitty/kittyWsAuthReconnect'

describe('recoverKittyWsAuthOrHardStop', () => {
  it('hard-stops when there is no authenticated user', async () => {
    const refreshAccessToken = vi.fn(async () => ({ success: true }))
    const onSessionExpired = vi.fn()
    const result = await recoverKittyWsAuthOrHardStop({
      hasAuthenticatedUser: false,
      refreshAccessToken,
      onSessionExpired,
    })
    expect(result).toBe('hard_stop')
    expect(refreshAccessToken).not.toHaveBeenCalled()
    expect(onSessionExpired).not.toHaveBeenCalled()
  })

  it('recovers when silent refresh succeeds', async () => {
    const onSessionExpired = vi.fn()
    const result = await recoverKittyWsAuthOrHardStop({
      hasAuthenticatedUser: true,
      refreshAccessToken: async () => ({ success: true }),
      onSessionExpired,
    })
    expect(result).toBe('recovered')
    expect(onSessionExpired).not.toHaveBeenCalled()
  })

  it('hard-stops and expires session when refresh fails', async () => {
    const onSessionExpired = vi.fn()
    const result = await recoverKittyWsAuthOrHardStop({
      hasAuthenticatedUser: true,
      refreshAccessToken: async () => ({ success: false }),
      onSessionExpired,
    })
    expect(result).toBe('hard_stop')
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })
})

describe('runKittyConnectWithAuthRecovery', () => {
  it('returns true on first successful connect without refreshing', async () => {
    const refreshAccessToken = vi.fn(async () => ({ success: true }))
    const connectOnce = vi.fn(async () => true)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped: vi.fn(),
      hasAuthenticatedUser: () => true,
      refreshAccessToken,
      onSessionExpired: vi.fn(),
      connectOnce,
    })
    expect(ok).toBe(true)
    expect(connectOnce).toHaveBeenCalledTimes(1)
    expect(refreshAccessToken).not.toHaveBeenCalled()
  })

  it('refreshes once and retries connect after the first failure', async () => {
    const connectOnce = vi
      .fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)
    const refreshAccessToken = vi.fn(async () => ({ success: true }))
    const markHardStopped = vi.fn()
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      refreshAccessToken,
      onSessionExpired: vi.fn(),
      connectOnce,
    })
    expect(ok).toBe(true)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(connectOnce).toHaveBeenCalledTimes(2)
    expect(markHardStopped).not.toHaveBeenCalled()
  })

  it('hard-stops the reconnect loop when refresh fails', async () => {
    const markHardStopped = vi.fn()
    const onSessionExpired = vi.fn()
    const connectOnce = vi.fn(async () => false)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => false,
      markHardStopped,
      hasAuthenticatedUser: () => true,
      refreshAccessToken: async () => ({ success: false }),
      onSessionExpired,
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(connectOnce).toHaveBeenCalledTimes(1)
    expect(markHardStopped).toHaveBeenCalledTimes(1)
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })

  it('does not connect when already hard-stopped', async () => {
    const connectOnce = vi.fn(async () => true)
    const ok = await runKittyConnectWithAuthRecovery({
      isHardStopped: () => true,
      markHardStopped: vi.fn(),
      hasAuthenticatedUser: () => true,
      refreshAccessToken: async () => ({ success: true }),
      onSessionExpired: vi.fn(),
      connectOnce,
    })
    expect(ok).toBe(false)
    expect(connectOnce).not.toHaveBeenCalled()
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
