/** Vitest — admin error collection clipboard dump formatting. */

import { describe, expect, it } from 'vitest'

import {
  formatAdminErrorEventsDump,
  formatAdminErrorGroupsDump,
} from '@/utils/admin/formatAdminErrorDump'

const filters = {
  view: 'events' as const,
  hours: 24,
  severity: 'error',
  source: '',
  page: 1,
  totalPages: 2,
  total: 60,
}

describe('formatAdminErrorEventsDump', () => {
  it('includes full fields and stacktrace for each event', () => {
    const text = formatAdminErrorEventsDump({
      exportedAt: '2026-08-01T12:00:00.000Z',
      filters,
      summary: {
        total_events_24h: 12,
        total_events_7d: 40,
        by_severity_24h: { error: 10 },
        by_source_24h: { application: 12 },
        top_groups_24h: [],
        alert_config: { webhook_configured: true, dingtalk_configured: false },
      },
      events: [
        {
          id: 7,
          group_id: 3,
          fingerprint: 'abc123fingerprint',
          severity: 'error',
          source: 'application',
          component: 'routers.api.diagrams',
          exception_type: 'ValueError',
          message: 'bad payload',
          request_id: 'req-1',
          user_id: 42,
          http_path: '/api/diagrams',
          http_status: 500,
          created_at: '2026-08-01T11:00:00.000Z',
          tags: { env: 'prod' },
          stacktrace: 'Traceback (most recent call last):\n  ValueError: bad payload',
        },
      ],
      truncated: true,
    })

    expect(text).toContain('# MindGraph Error Collection Dump')
    expect(text).toContain('severity=error')
    expect(text).toContain('source=all')
    expect(text).toContain('id: 7')
    expect(text).toContain('user_id: 42')
    expect(text).toContain('bad payload')
    expect(text).toContain('"env": "prod"')
    expect(text).toContain('Traceback (most recent call last):')
    expect(text).toContain('dump truncated to first')
  })

  it('renders empty events dump without separators body', () => {
    const text = formatAdminErrorEventsDump({
      exportedAt: '2026-08-01T12:00:00.000Z',
      filters,
      events: [],
    })
    expect(text).toContain('(no events)')
  })
})

describe('formatAdminErrorGroupsDump', () => {
  it('includes group fields and sample message', () => {
    const text = formatAdminErrorGroupsDump({
      exportedAt: '2026-08-01T12:00:00.000Z',
      filters: { ...filters, view: 'groups' },
      groups: [
        {
          id: 9,
          fingerprint: 'fp-group-1',
          severity: 'warning',
          source: 'llm',
          component: 'services.llm',
          exception_type: 'TimeoutError',
          sample_message: 'upstream timeout',
          occurrence_count: 15,
          first_seen_at: '2026-07-30T00:00:00.000Z',
          last_seen_at: '2026-08-01T10:00:00.000Z',
          muted: false,
        },
      ],
    })

    expect(text).toContain('View: groups')
    expect(text).toContain('occurrence_count: 15')
    expect(text).toContain('upstream timeout')
    expect(text).toContain('muted: false')
  })
})
