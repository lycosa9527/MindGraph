import { describe, expect, it } from 'vitest'

import { interpretSessionStatusResponse } from '@/utils/sessionStatusOutcome'

describe('interpretSessionStatusResponse', () => {
  it('treats HTTP 401 as expiry, not a device-limit kick', () => {
    expect(interpretSessionStatusResponse(401, null)).toEqual({ kind: 'expired' })
    expect(
      interpretSessionStatusResponse(401, {
        status: 'invalidated',
        message: 'Session ended: maximum device limit exceeded',
      })
    ).toEqual({ kind: 'expired' })
  })

  it('keeps explicit invalidated payloads as a kick', () => {
    expect(
      interpretSessionStatusResponse(200, {
        status: 'invalidated',
        message: 'Session ended: maximum device limit exceeded',
        reason: 'max_devices_exceeded',
      })
    ).toEqual({
      kind: 'invalidated',
      message: 'Session ended: maximum device limit exceeded',
      reason: 'max_devices_exceeded',
    })
  })

  it('ignores active and unauthenticated bodies', () => {
    expect(interpretSessionStatusResponse(200, { status: 'active' })).toEqual({ kind: 'noop' })
    expect(interpretSessionStatusResponse(200, { status: 'unauthenticated' })).toEqual({
      kind: 'noop',
    })
    expect(interpretSessionStatusResponse(503, null)).toEqual({ kind: 'noop' })
  })
})
