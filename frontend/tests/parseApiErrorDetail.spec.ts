import { describe, expect, it } from 'vitest'

import { parseApiErrorDetail } from '@/utils/apiClient'

describe('parseApiErrorDetail', () => {
  it('reads string detail', () => {
    expect(parseApiErrorDetail({ detail: 'boom' }, 'fallback')).toBe('boom')
  })

  it('reads object detail message/code', () => {
    expect(
      parseApiErrorDetail(
        { detail: { code: 'doc_summary_content_too_long', message: 'too long' } },
        'fallback'
      )
    ).toBe('too long')
    expect(
      parseApiErrorDetail({ detail: { code: 'doc_summary_content_too_long' } }, 'fallback')
    ).toBe('doc_summary_content_too_long')
  })

  it('falls back when detail is missing', () => {
    expect(parseApiErrorDetail(null, 'fallback')).toBe('fallback')
  })

  it('drops API field paths from validation lines', () => {
    expect(
      parseApiErrorDetail(
        {
          detail: [
            'body.name: Value error, Name must be at least 2 characters and must not contain digits.',
            'body.phone: Phone number is too short (2 digits). Must be exactly 11 digits starting with 1.',
          ],
        },
        'fallback'
      )
    ).toBe(
      'Name must be at least 2 characters and must not contain digits.\nPhone number is too short (2 digits). Must be exactly 11 digits starting with 1.'
    )
  })
})
