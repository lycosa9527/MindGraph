import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  TEST_SERVER_BANNER_DAY_KEY,
  hasShownTestServerBannerToday,
  localCalendarDayKey,
  markTestServerBannerShownToday,
  shouldShowTestServerBannerOnVisit,
} from '@/utils/testServerBanner'

describe('testServerBanner', () => {
  afterEach(() => {
    localStorage.removeItem(TEST_SERVER_BANNER_DAY_KEY)
    vi.useRealTimers()
  })

  it('localCalendarDayKey formats YYYY-MM-DD', () => {
    expect(localCalendarDayKey(new Date(2026, 6, 10))).toBe('2026-07-10')
  })

  it('defaults to not shown today', () => {
    expect(hasShownTestServerBannerToday()).toBe(false)
    expect(shouldShowTestServerBannerOnVisit()).toBe(true)
  })

  it('marks and gates the same calendar day', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 10, 9, 0, 0))
    markTestServerBannerShownToday()
    expect(hasShownTestServerBannerToday()).toBe(true)
    expect(shouldShowTestServerBannerOnVisit()).toBe(false)
    expect(shouldShowTestServerBannerOnVisit('/mindmate')).toBe(false)
  })

  it('always shows on /auth and /login even after daily dismiss', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 10, 9, 0, 0))
    markTestServerBannerShownToday()
    expect(shouldShowTestServerBannerOnVisit('/auth')).toBe(true)
    expect(shouldShowTestServerBannerOnVisit('/login')).toBe(true)
  })

  it('shows again on the next calendar day', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 10, 23, 0, 0))
    markTestServerBannerShownToday()
    expect(shouldShowTestServerBannerOnVisit()).toBe(false)

    vi.setSystemTime(new Date(2026, 6, 11, 0, 5, 0))
    expect(shouldShowTestServerBannerOnVisit()).toBe(true)
  })
})
