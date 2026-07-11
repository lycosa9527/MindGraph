/**
 * Persistence helpers for SwissWarningModal cadence (test-server banner).
 *
 * Show when:
 * - once per calendar day on normal visits
 * - every interactive login
 * - every visit to /auth (and /login) — always, ignoring the daily gate
 *
 * Modal: @/components/common/SwissWarningModal.vue
 */

import { isGuestAuthPath } from '@/utils/authRedirect'

export const TEST_SERVER_BANNER_DAY_KEY = 'mg_test_server_banner_day'

export function localCalendarDayKey(date: Date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function hasShownTestServerBannerToday(): boolean {
  try {
    return localStorage.getItem(TEST_SERVER_BANNER_DAY_KEY) === localCalendarDayKey()
  } catch {
    return false
  }
}

export function markTestServerBannerShownToday(): void {
  try {
    localStorage.setItem(TEST_SERVER_BANNER_DAY_KEY, localCalendarDayKey())
  } catch {
    // Ignore quota / private-mode failures; modal may reappear.
  }
}

export function shouldShowTestServerBannerOnVisit(pathname?: string): boolean {
  if (pathname !== undefined && isGuestAuthPath(pathname)) {
    return true
  }
  return !hasShownTestServerBannerToday()
}
