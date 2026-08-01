/**
 * Build a full admin error-collection dump (with stacktraces) for clipboard export.
 */

import {
  fetchAdminErrorEventDetail,
  fetchAdminErrorEvents,
  fetchAdminErrorGroups,
  type AdminErrorEventItem,
  type AdminErrorSummaryResponse,
} from '@/composables/queries/adminApi'
import {
  formatAdminErrorEventsDump,
  formatAdminErrorGroupsDump,
  type AdminErrorDumpFilters,
  type AdminErrorEventDetail,
} from '@/utils/admin/formatAdminErrorDump'

/** API page_size upper bound — one dump fetch stops here. */
export const ADMIN_ERROR_COPY_PAGE_SIZE = 200

/** Parallel detail fetches; keeps admin API load bounded. */
export const ADMIN_ERROR_DETAIL_CONCURRENCY = 8

export type AdminErrorCopyView = 'events' | 'groups'

export interface AdminErrorCopyQuery {
  view: AdminErrorCopyView
  hours: number
  severity: string
  source: string
  summary?: AdminErrorSummaryResponse | null
  signal?: AbortSignal
  exportedAt?: string
  fetchEvents?: typeof fetchAdminErrorEvents
  fetchGroups?: typeof fetchAdminErrorGroups
  fetchEventDetail?: typeof fetchAdminErrorEventDetail
  detailConcurrency?: number
  pageSize?: number
}

export type AdminErrorCopyResult =
  | { kind: 'empty' }
  | {
      kind: 'ok'
      text: string
      count: number
      total: number
      truncated: boolean
      failedDetails: number
    }

function rejectionMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message) {
    return reason.message
  }
  return 'unknown error'
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
}

export async function loadAdminErrorEventDetails(
  rows: AdminErrorEventItem[],
  options: {
    fetchEventDetail?: typeof fetchAdminErrorEventDetail
    concurrency?: number
    signal?: AbortSignal
  } = {}
): Promise<{ events: AdminErrorEventDetail[]; failedCount: number }> {
  const fetchDetail = options.fetchEventDetail ?? fetchAdminErrorEventDetail
  const concurrency = Math.max(1, options.concurrency ?? ADMIN_ERROR_DETAIL_CONCURRENCY)
  const signal = options.signal
  const events: AdminErrorEventDetail[] = new Array(rows.length)
  let failedCount = 0
  let nextIndex = 0

  async function worker(): Promise<void> {
    while (nextIndex < rows.length) {
      throwIfAborted(signal)
      const index = nextIndex
      nextIndex += 1
      const row = rows[index]
      try {
        events[index] = await fetchDetail(row.id, signal)
      } catch (error) {
        throwIfAborted(signal)
        failedCount += 1
        events[index] = {
          ...row,
          stacktrace: `[failed to load stacktrace: ${rejectionMessage(error)}]`,
        }
      }
    }
  }

  const workerCount = Math.min(concurrency, Math.max(rows.length, 1))
  await Promise.all(Array.from({ length: workerCount }, () => worker()))
  return { events, failedCount }
}

function dumpFilters(
  query: AdminErrorCopyQuery,
  total: number,
  totalPages: number
): AdminErrorDumpFilters {
  return {
    view: query.view,
    hours: query.hours,
    severity: query.severity,
    source: query.source,
    page: 1,
    totalPages,
    total,
  }
}

export async function buildAdminErrorCollectionDump(
  query: AdminErrorCopyQuery
): Promise<AdminErrorCopyResult> {
  throwIfAborted(query.signal)
  const pageSize = query.pageSize ?? ADMIN_ERROR_COPY_PAGE_SIZE
  const exportedAt = query.exportedAt ?? new Date().toISOString()
  const listQuery = {
    page: 1,
    page_size: pageSize,
    hours: query.hours,
    severity: query.severity || undefined,
    source: query.source || undefined,
  }
  const fetchEvents = query.fetchEvents ?? fetchAdminErrorEvents
  const fetchGroups = query.fetchGroups ?? fetchAdminErrorGroups

  if (query.view === 'events') {
    const response = await fetchEvents(listQuery, query.signal)
    throwIfAborted(query.signal)
    if (response.events.length === 0) {
      return { kind: 'empty' }
    }
    const { events, failedCount } = await loadAdminErrorEventDetails(response.events, {
      fetchEventDetail: query.fetchEventDetail,
      concurrency: query.detailConcurrency,
      signal: query.signal,
    })
    const truncated = response.total > events.length
    return {
      kind: 'ok',
      text: formatAdminErrorEventsDump({
        exportedAt,
        filters: dumpFilters(query, response.total, response.total_pages),
        summary: query.summary,
        events,
        truncated,
        failedDetails: failedCount,
        fetchLimit: pageSize,
      }),
      count: events.length,
      total: response.total,
      truncated,
      failedDetails: failedCount,
    }
  }

  const response = await fetchGroups(listQuery, query.signal)
  throwIfAborted(query.signal)
  if (response.groups.length === 0) {
    return { kind: 'empty' }
  }
  const truncated = response.total > response.groups.length
  return {
    kind: 'ok',
    text: formatAdminErrorGroupsDump({
      exportedAt,
      filters: dumpFilters(query, response.total, response.total_pages),
      summary: query.summary,
      groups: response.groups,
      truncated,
      fetchLimit: pageSize,
    }),
    count: response.groups.length,
    total: response.total,
    truncated,
    failedDetails: 0,
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
