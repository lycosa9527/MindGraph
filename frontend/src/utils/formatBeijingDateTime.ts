/**
 * Format API timestamps as Asia/Shanghai (Beijing) local time for admin tables.
 */
const BEIJING_TIME_ZONE = 'Asia/Shanghai'

function parseTimestamp(value: string): Date | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  return parsed
}

/**
 * Date-only calendar day from an ISO timestamp or `YYYY-MM-DD` string (Beijing).
 * Prefer the leading date part when present so end-of-day expiry stays on that day.
 */
function beijingCalendarDate(value: string): Date | null {
  const trimmed = value.trim()
  const datePartMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (datePartMatch) {
    const year = Number(datePartMatch[1])
    const month = Number(datePartMatch[2])
    const day = Number(datePartMatch[3])
    const local = new Date(year, month - 1, day)
    if (
      local.getFullYear() === year &&
      local.getMonth() === month - 1 &&
      local.getDate() === day
    ) {
      return local
    }
  }
  return parseTimestamp(trimmed)
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
  const parsed = beijingCalendarDate(String(value))
  if (!parsed) {
    return String(value)
  }
  return parsed.toLocaleDateString(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
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
  const parsed = parseTimestamp(String(value))
  if (!parsed) {
    return String(value)
  }
  return parsed.toLocaleString(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: BEIJING_TIME_ZONE,
  })
}
