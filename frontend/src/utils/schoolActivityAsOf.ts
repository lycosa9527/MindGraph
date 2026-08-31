/**
 * Format school-activity snapshot timestamps in Beijing wall clock.
 */

export function beijingCalendarParts(now: Date = new Date()): { year: number; month: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now)
  const year = Number(parts.find((part) => part.type === 'year')?.value ?? now.getFullYear())
  const month = Number(parts.find((part) => part.type === 'month')?.value ?? now.getMonth() + 1)
  return { year, month }
}

export function beijingCalendarYear(now: Date = new Date()): number {
  return beijingCalendarParts(now).year
}

export function formatBeijingSnapshotTime(isoUtc: string): string {
  const parsed = new Date(isoUtc)
  if (Number.isNaN(parsed.getTime())) {
    return isoUtc
  }
  const formatted = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
  return formatted.replace('T', ' ')
}
