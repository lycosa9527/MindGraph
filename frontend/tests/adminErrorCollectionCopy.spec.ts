/** Vitest — admin error collection dump builder (batched details + truncate). */

import { describe, expect, it, vi } from 'vitest'

import {
  ADMIN_ERROR_COPY_PAGE_SIZE,
  buildAdminErrorCollectionDump,
  loadAdminErrorEventDetails,
} from '@/utils/admin/adminErrorCollectionCopy'

describe('loadAdminErrorEventDetails', () => {
  it('loads details with bounded concurrency and records failures', async () => {
    const rows = [
      {
        id: 1,
        group_id: 1,
        fingerprint: 'fp1',
        severity: 'error',
        source: 'application',
        component: 'a',
        exception_type: 'Error',
        message: 'one',
        created_at: '2026-08-01T00:00:00.000Z',
      },
      {
        id: 2,
        group_id: 1,
        fingerprint: 'fp2',
        severity: 'error',
        source: 'application',
        component: 'b',
        exception_type: 'Error',
        message: 'two',
        created_at: '2026-08-01T00:01:00.000Z',
      },
    ]
    const fetchEventDetail = vi.fn(async (id: number) => {
      if (id === 2) {
        throw new Error('boom')
      }
      return { ...rows[0], id, stacktrace: `stack-${id}` }
    })

    const { events, failedCount } = await loadAdminErrorEventDetails(rows, {
      fetchEventDetail,
      concurrency: 1,
    })

    expect(failedCount).toBe(1)
    expect(events[0].stacktrace).toBe('stack-1')
    expect(events[1].stacktrace).toContain('failed to load stacktrace: boom')
    expect(fetchEventDetail).toHaveBeenCalledTimes(2)
  })
})

describe('buildAdminErrorCollectionDump', () => {
  it('builds a full events dump including path message and stacktrace', async () => {
    const event = {
      id: 9,
      group_id: 3,
      fingerprint: 'fp-9',
      severity: 'error',
      source: 'application',
      component: 'routers.api',
      exception_type: 'ValueError',
      message: 'bad payload',
      http_path: '/api/diagrams',
      http_status: 500,
      request_id: 'req-9',
      user_id: 7,
      created_at: '2026-08-01T10:00:00.000Z',
      tags: { k: 'v' },
      stacktrace: 'Traceback\nValueError',
    }
    const result = await buildAdminErrorCollectionDump({
      view: 'events',
      hours: 24,
      severity: '',
      source: '',
      exportedAt: '2026-08-01T12:00:00.000Z',
      fetchEvents: vi.fn(async () => ({
        events: [event],
        page: 1,
        page_size: ADMIN_ERROR_COPY_PAGE_SIZE,
        total: 1,
        total_pages: 1,
      })),
      fetchEventDetail: vi.fn(async () => event),
    })

    expect(result.kind).toBe('ok')
    if (result.kind !== 'ok') {
      return
    }
    expect(result.truncated).toBe(false)
    expect(result.text).toContain('http_path: /api/diagrams')
    expect(result.text).toContain('bad payload')
    expect(result.text).toContain('Traceback')
    expect(result.text).toContain('"k": "v"')
  })

  it('marks truncated dumps when total exceeds fetch limit', async () => {
    const event = {
      id: 1,
      group_id: 1,
      fingerprint: 'fp',
      severity: 'error',
      source: 'llm',
      component: 'c',
      exception_type: 'Error',
      message: 'x',
      created_at: '2026-08-01T10:00:00.000Z',
      stacktrace: 'stack',
    }
    const result = await buildAdminErrorCollectionDump({
      view: 'events',
      hours: 168,
      severity: 'error',
      source: 'llm',
      pageSize: 1,
      exportedAt: '2026-08-01T12:00:00.000Z',
      fetchEvents: vi.fn(async () => ({
        events: [event],
        page: 1,
        page_size: 1,
        total: 5,
        total_pages: 5,
      })),
      fetchEventDetail: vi.fn(async () => event),
    })

    expect(result.kind).toBe('ok')
    if (result.kind !== 'ok') {
      return
    }
    expect(result.truncated).toBe(true)
    expect(result.text).toContain('dump truncated to first 1 of 5 matches')
  })
})
