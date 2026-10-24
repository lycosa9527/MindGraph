/**
 * Beijing (Asia/Shanghai) clock for user-visible times.
 *
 * API timestamps without an offset are UTC instants. China has no daylight
 * saving time, so a fixed +08:00 offset matches Asia/Shanghai.
 */

export const BEIJING_TIME_ZONE = 'Asia/Shanghai'

const ZONE_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/i
const DAY_MS = 24 * 60 * 60 * 1000

export type BeijingWall = {
  year: string
  month: string
  day: string
  hour: string
  minute: string
  second: string
}

function wallPart(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((part) => part.type === type)?.value ?? ''
}

/** Parse an API instant. A datetime with no offset is UTC. A date-only string is UTC midnight. */
export function parseApiInstant(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === '') return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value === 'number') {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }
  const trimmed = value.trim()
  if (!trimmed) return null
  const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  let iso = normalized
  if (!ZONE_SUFFIX.test(normalized)) {
    iso = /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? `${normalized}T00:00:00Z` : `${normalized}Z`
  }
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/**
 * Parse a value that is already a Beijing wall clock (`YYYY-MM-DD` or
 * `YYYY-MM-DD HH:mm`), such as admin trend labels built in Asia/Shanghai.
 */
export function parseBeijingWall(value: string): Date | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  if (ZONE_SUFFIX.test(normalized)) {
    const parsed = new Date(normalized)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }
  const iso = /^\d{4}-\d{2}-\d{2}$/.test(normalized)
    ? `${normalized}T00:00:00+08:00`
    : `${normalized}+08:00`
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function beijingWallClock(date: Date = new Date()): BeijingWall {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BEIJING_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const hour = wallPart(parts, 'hour')
  return {
    year: wallPart(parts, 'year'),
    month: wallPart(parts, 'month'),
    day: wallPart(parts, 'day'),
    hour: hour === '24' ? '00' : hour,
    minute: wallPart(parts, 'minute'),
    second: wallPart(parts, 'second'),
  }
}

export function beijingHour(now: Date = new Date()): number {
  const hour = Number(beijingWallClock(now).hour)
  return Number.isFinite(hour) ? hour : 0
}

export function beijingDayStartMs(now: Date = new Date()): number {
  const wall = beijingWallClock(now)
  return Date.parse(`${wall.year}-${wall.month}-${wall.day}T00:00:00+08:00`)
}

export function beijingRecentDayStarts(now: Date = new Date()): {
  todayStart: number
  yesterdayStart: number
  weekStart: number
} {
  const todayStart = beijingDayStartMs(now)
  return {
    todayStart,
    yesterdayStart: todayStart - DAY_MS,
    weekStart: todayStart - 7 * DAY_MS,
  }
}

/** Whole Beijing calendar days from `earlier` to `later` (0 = same day). */
export function beijingCalendarDaysBetween(earlier: Date, later: Date): number {
  return Math.round((beijingDayStartMs(later) - beijingDayStartMs(earlier)) / DAY_MS)
}

const DEFAULT_DATE_TIME: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
}

/** Format an instant in Asia/Shanghai. Empty string when the value is not a time. */
export function formatInBeijing(
  value: string | number | Date | null | undefined,
  locale?: Intl.LocalesArgument,
  options?: Intl.DateTimeFormatOptions
): string {
  const date = parseApiInstant(value)
  if (!date) return ''
  const formatOptions = options
    ? { ...options, timeZone: BEIJING_TIME_ZONE }
    : { ...DEFAULT_DATE_TIME, timeZone: BEIJING_TIME_ZONE }
  return new Intl.DateTimeFormat(locale, formatOptions).format(date)
}
