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
