import { describe, expect, it } from 'vitest'

import {
  computeMindmateCollabReconnectDelayMs,
  mindmateCollabPermanentFailureLocaleKey,
  shouldScheduleMindmateCollabReconnect,
} from '@/utils/mindmateCollabReconnect'
import { shouldReconnectMindmateCollab } from '@/utils/mindmateCollabSessions'

describe('shouldReconnectMindmateCollab', () => {
  it('does not reconnect after idle shutdown 4010', () => {
    expect(shouldReconnectMindmateCollab(4010)).toBe(false)
  })

  it('does not reconnect after host stop 4011', () => {
    expect(shouldReconnectMindmateCollab(4011)).toBe(false)
  })

  it('does not reconnect after duplicate tab 4003', () => {
    expect(shouldReconnectMindmateCollab(4003)).toBe(false)
  })

  it('does not reconnect after policy violation 1008', () => {
    expect(shouldReconnectMindmateCollab(1008)).toBe(false)
  })

  it('does not reconnect after connection cap 4029', () => {
    expect(shouldReconnectMindmateCollab(4029)).toBe(false)
  })

  it('reconnects on abnormal disconnect', () => {
    expect(shouldReconnectMindmateCollab(1006)).toBe(true)
  })
})

describe('mindmateCollabReconnect helpers', () => {
  it('caps exponential backoff delay', () => {
    expect(computeMindmateCollabReconnectDelayMs(10)).toBeLessThanOrEqual(30000)
  })

  it('does not schedule reconnect for permanent failures', () => {
    expect(shouldScheduleMindmateCollabReconnect(0, 1008)).toBe(false)
    expect(shouldScheduleMindmateCollabReconnect(0, 4029)).toBe(false)
  })

  it('maps auth-related 1008 reasons', () => {
    expect(
      mindmateCollabPermanentFailureLocaleKey(1008, 'Unauthorized'),
    ).toBe('mindmate.collabConnectionAuthFailed')
  })

  it('maps invalid room 1008 reasons', () => {
    expect(
      mindmateCollabPermanentFailureLocaleKey(1008, 'Invalid room'),
    ).toBe('mindmate.collabConnectionDenied')
  })

  it('maps connection limit close code', () => {
    expect(mindmateCollabPermanentFailureLocaleKey(4029, '')).toBe(
      'mindmate.collabConnectionLimit',
    )
  })
})
