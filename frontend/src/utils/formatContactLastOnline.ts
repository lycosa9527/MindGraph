/**
 * Relative labels for "online … ago" in the workshop contacts list.
 */
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

export function formatContactLastOnlineLabel(
  lastSeenAtMs: number,
  nowMs: number,
  translate: (key: string) => string,
): string {
  const diff = nowMs - lastSeenAtMs
  if (diff < 0 || diff > LAST_SEEN_ONLINE_MAX_AGE_MS) {
    return ''
  }
  const minuteMs = 60 * 1000
  const hourMs = 60 * minuteMs
  const dayMs = 24 * hourMs
  if (diff < minuteMs) {
    return translate('workshop.contactLastOnlineJustNow')
  }
  if (diff < hourMs) {
    const n = Math.max(1, Math.floor(diff / minuteMs))
    return translate('workshop.contactLastOnlineMinutes').replace('{n}', String(n))
  }
  if (diff < dayMs) {
    const n = Math.max(1, Math.floor(diff / hourMs))
    return translate('workshop.contactLastOnlineHours').replace('{n}', String(n))
  }
  const n = Math.max(1, Math.floor(diff / dayMs))
  return translate('workshop.contactLastOnlineDays').replace('{n}', String(n))
}
