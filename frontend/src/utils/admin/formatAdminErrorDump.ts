/**
 * Format admin error-collection rows into a plain-text dump for clipboard / Cursor.
 */

import type {
  AdminErrorEventItem,
  AdminErrorGroupItem,
  AdminErrorSummaryResponse,
} from '@/composables/queries/adminApi'

export type AdminErrorEventDetail = AdminErrorEventItem & {
  stacktrace?: string | null
}

export interface AdminErrorDumpFilters {
  view: 'events' | 'groups'
  hours: number
  severity: string
  source: string
  page: number
  totalPages: number
  total: number
}

export interface FormatAdminErrorEventsDumpInput {
  exportedAt: string
  filters: AdminErrorDumpFilters
  summary?: AdminErrorSummaryResponse | null
  events: AdminErrorEventDetail[]
  truncated?: boolean
  failedDetails?: number
  fetchLimit?: number
}

export interface FormatAdminErrorGroupsDumpInput {
  exportedAt: string
  filters: AdminErrorDumpFilters
  summary?: AdminErrorSummaryResponse | null
  groups: AdminErrorGroupItem[]
  truncated?: boolean
  fetchLimit?: number
}

function formatOptional(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return String(value)
}

function formatTags(tags: Record<string, unknown> | null | undefined): string {
  if (!tags || Object.keys(tags).length === 0) {
    return '—'
  }
  try {
    return JSON.stringify(tags, null, 2)
  } catch {
    return '—'
  }
}

function formatSummaryBlock(summary?: AdminErrorSummaryResponse | null): string {
  if (!summary) {
    return 'Summary: (not loaded)'
  }
  const lines = [
    `Summary 24h events: ${summary.total_events_24h}`,
    `Summary 7d events: ${summary.total_events_7d}`,
    `By severity 24h: ${JSON.stringify(summary.by_severity_24h ?? {})}`,
    `By source 24h: ${JSON.stringify(summary.by_source_24h ?? {})}`,
    `Alert webhook configured: ${Boolean(summary.alert_config?.webhook_configured)}`,
    `Alert DingTalk configured: ${Boolean(summary.alert_config?.dingtalk_configured)}`,
  ]
  return lines.join('\n')
}

function formatFiltersBlock(filters: AdminErrorDumpFilters): string {
  const severity = filters.severity || 'all'
  const source = filters.source || 'all'
  return [
    `View: ${filters.view}`,
    `Filters: hours=${filters.hours} severity=${severity} source=${source}`,
    `Page: ${filters.page}/${filters.totalPages} · total matching=${filters.total}`,
  ].join('\n')
}

function formatHeader(
  exportedAt: string,
  filters: AdminErrorDumpFilters,
  summary?: AdminErrorSummaryResponse | null,
  options?: { truncated?: boolean; failedDetails?: number; fetchLimit?: number }
): string {
  const parts = [
    '# MindGraph Error Collection Dump',
    `Exported: ${exportedAt}`,
    formatFiltersBlock(filters),
    formatSummaryBlock(summary),
  ]
  if (options?.truncated) {
    const limit = options.fetchLimit ?? filters.total
    parts.push(
      `Note: dump truncated to first ${limit} of ${filters.total} matches; refine filters for the rest.`
    )
  }
  if (options?.failedDetails && options.failedDetails > 0) {
    parts.push(
      `Note: ${options.failedDetails} event stacktrace(s) failed to load; list fields are still included.`
    )
  }
  return parts.join('\n')
}

function formatEventBlock(event: AdminErrorEventDetail, index: number, total: number): string {
  const lines = [
    `## Event ${index}/${total} — id=${event.id}`,
    `id: ${event.id}`,
    `group_id: ${event.group_id}`,
    `created_at: ${event.created_at}`,
    `severity: ${event.severity}`,
    `source: ${event.source}`,
    `component: ${event.component}`,
    `exception_type: ${event.exception_type}`,
    `fingerprint: ${event.fingerprint}`,
    `http_path: ${formatOptional(event.http_path)}`,
    `http_status: ${formatOptional(event.http_status)}`,
    `request_id: ${formatOptional(event.request_id)}`,
    `user_id: ${formatOptional(event.user_id)}`,
    'message:',
    event.message || '—',
    'tags:',
    formatTags(event.tags),
    'stacktrace:',
    event.stacktrace?.trim() ? event.stacktrace : '—',
  ]
  return lines.join('\n')
}

function formatGroupBlock(group: AdminErrorGroupItem, index: number, total: number): string {
  const lines = [
    `## Group ${index}/${total} — id=${group.id}`,
    `id: ${group.id}`,
    `fingerprint: ${group.fingerprint}`,
    `severity: ${group.severity}`,
    `source: ${group.source}`,
    `component: ${group.component}`,
    `exception_type: ${group.exception_type}`,
    `occurrence_count: ${group.occurrence_count}`,
    `first_seen_at: ${group.first_seen_at}`,
    `last_seen_at: ${group.last_seen_at}`,
    `muted: ${group.muted}`,
    'sample_message:',
    group.sample_message || '—',
  ]
  return lines.join('\n')
}

const SEPARATOR = `${'='.repeat(80)}`

export function formatAdminErrorEventsDump(input: FormatAdminErrorEventsDumpInput): string {
  const { exportedAt, filters, summary, events, truncated, failedDetails, fetchLimit } = input
  const header = formatHeader(exportedAt, filters, summary, {
    truncated,
    failedDetails,
    fetchLimit,
  })
  if (events.length === 0) {
    return `${header}\n\n(no events)\n`
  }
  const body = events
    .map((event, i) => formatEventBlock(event, i + 1, events.length))
    .join(`\n${SEPARATOR}\n`)
  return `${header}\n\n${SEPARATOR}\n${body}\n${SEPARATOR}\n`
}

export function formatAdminErrorGroupsDump(input: FormatAdminErrorGroupsDumpInput): string {
  const { exportedAt, filters, summary, groups, truncated, fetchLimit } = input
  const header = formatHeader(exportedAt, filters, summary, { truncated, fetchLimit })
  if (groups.length === 0) {
    return `${header}\n\n(no groups)\n`
  }
  const body = groups
    .map((group, i) => formatGroupBlock(group, i + 1, groups.length))
    .join(`\n${SEPARATOR}\n`)
  return `${header}\n\n${SEPARATOR}\n${body}\n${SEPARATOR}\n`
}
