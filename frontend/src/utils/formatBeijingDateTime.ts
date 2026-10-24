/**
 * Format API timestamps as Asia/Shanghai (Beijing) local time for admin tables.
 */
import { formatInBeijing, parseApiInstant, parseBeijingWall } from '@/utils/beijingClock'

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}

/**
 * Calendar day for an expiry `YYYY-MM-DD` (or a timestamp whose leading date is that day).
 * Noon in Beijing keeps the day stable in every browser timezone.
 */
function expiryCalendarInstant(value: string): Date | null {
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) {
    return parseApiInstant(value)
  }
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const probe = new Date(Date.UTC(year, month - 1, day))
  const realDay =
    probe.getUTCFullYear() === year &&
    probe.getUTCMonth() === month - 1 &&
    probe.getUTCDate() === day
  if (!realDay) {
    return null
  }
  return parseBeijingWall(`${match[1]}-${match[2]}-${match[3]}T12:00:00`)
}

/**
 * @param locale BCP 47 locale (e.g. zh-CN, en-US) for display labels
 */
export function formatBeijingDate(
  value: string | null | undefined,
  locale: string = 'zh-CN'
): string {
  if (value == null || !String(value).trim()) {
    return '—'
  }
  const instant = expiryCalendarInstant(String(value))
  if (!instant) {
    return String(value)
  }
  return formatInBeijing(instant, locale, DATE_OPTIONS) || String(value)
}

/**
 * @param locale BCP 47 locale (e.g. zh-CN, en-US) for display labels
 */
export function formatBeijingDateTime(
  value: string | null | undefined,
  locale: string = 'zh-CN'
): string {
  if (value == null || !String(value).trim()) {
    return '—'
  }
  return formatInBeijing(String(value), locale) || String(value)
}
