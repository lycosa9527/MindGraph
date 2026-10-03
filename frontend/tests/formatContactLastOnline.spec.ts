import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLanguage } from '@/composables/core/useLanguage'
import { loadLocaleMessages, setI18nLocale } from '@/i18n'
import { formatContactLastOnlineLabel } from '@/utils/formatContactLastOnline'
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS
const now = Date.parse('2026-10-03T15:00:00Z')

function label(ageMs: number): string {
  const { t } = useLanguage()
  return formatContactLastOnlineLabel(now - ageMs, now, (key, named) =>
    named ? t(key, named) : t(key)
  )
}

describe('formatContactLastOnlineLabel', () => {
  beforeEach(async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
    await loadLocaleMessages('zh')
    setI18nLocale('zh')
  })

  it('fills the count through useLanguage, which vue-i18n would otherwise drop', () => {
    expect(label(3 * HOUR_MS)).toBe('3小时前在线')
    expect(label(12 * MINUTE_MS)).toBe('12分钟前在线')
    expect(label(2 * DAY_MS)).toBe('2天前在线')
  })

  it('switches buckets at 60 minutes and 24 hours', () => {
    expect(label(59 * MINUTE_MS)).toBe('59分钟前在线')
    expect(label(60 * MINUTE_MS)).toBe('1小时前在线')
    expect(label(23 * HOUR_MS)).toBe('23小时前在线')
    expect(label(24 * HOUR_MS)).toBe('1天前在线')
  })

  it('uses just-now inside the first minute', () => {
    expect(label(20_000)).toBe('刚刚在线')
  })

  it('hides future timestamps and ages past the recently-online window', () => {
    expect(label(-HOUR_MS)).toBe('')
    expect(label(LAST_SEEN_ONLINE_MAX_AGE_MS)).toBe('7天前在线')
    expect(label(LAST_SEEN_ONLINE_MAX_AGE_MS + 1)).toBe('')
  })

  it('fills the English catalog the same way', () => {
    setI18nLocale('en')
    expect(label(3 * HOUR_MS)).toBe('Online 3 hours ago')
  })
})
