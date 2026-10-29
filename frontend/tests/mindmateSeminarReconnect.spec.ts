import { describe, expect, it } from 'vitest'

import {
  computeMindmateSeminarReconnectDelayMs,
  mindmateSeminarPermanentFailureLocaleKey,
  shouldScheduleMindmateSeminarReconnect,
} from '@/utils/mindmateSeminarReconnect'
import { shouldReconnectMindmateSeminar } from '@/utils/mindmateSeminarSessions'

describe('shouldReconnectMindmateSeminar', () => {
  it('does not reconnect after idle shutdown 4010', () => {
    expect(shouldReconnectMindmateSeminar(4010)).toBe(false)
  })

  it('does not reconnect after host stop 4011', () => {
    expect(shouldReconnectMindmateSeminar(4011)).toBe(false)
  })

  it('does not reconnect after duplicate tab 4003', () => {
    expect(shouldReconnectMindmateSeminar(4003)).toBe(false)
  })

  it('does not reconnect after policy violation 1008', () => {
    expect(shouldReconnectMindmateSeminar(1008)).toBe(false)
  })

  it('does not reconnect after connection cap 4029', () => {
    expect(shouldReconnectMindmateSeminar(4029)).toBe(false)
  })

  it('reconnects on abnormal disconnect', () => {
    expect(shouldReconnectMindmateSeminar(1006)).toBe(true)
  })
})

describe('mindmateSeminarReconnect helpers', () => {
  it('caps exponential backoff delay', () => {
    expect(computeMindmateSeminarReconnectDelayMs(10)).toBeLessThanOrEqual(30000)
  })

  it('does not schedule reconnect for permanent failures', () => {
    expect(shouldScheduleMindmateSeminarReconnect(0, 1008)).toBe(false)
    expect(shouldScheduleMindmateSeminarReconnect(0, 4029)).toBe(false)
  })

  it('maps auth-related 1008 reasons', () => {
    expect(mindmateSeminarPermanentFailureLocaleKey(1008, 'Unauthorized')).toBe(
      'mindmate.collabConnectionAuthFailed'
    )
  })

  it('maps invalid room 1008 reasons', () => {
    expect(mindmateSeminarPermanentFailureLocaleKey(1008, 'Invalid room')).toBe(
      'mindmate.collabConnectionDenied'
    )
  })

  it('maps connection limit close code', () => {
    expect(mindmateSeminarPermanentFailureLocaleKey(4029, '')).toBe('mindmate.collabConnectionLimit')
  })
})
