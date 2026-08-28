import { describe, expect, it } from 'vitest'

import {
  DOC_SUMMARY_UPLOAD_ACCEPT,
  isContentFilterDetail,
} from '@/composables/mindMap/useMindMapDocumentSummary'

describe('DOC_SUMMARY_UPLOAD_ACCEPT', () => {
  it('includes legacy Office, spreadsheets, text, and webp', () => {
    const accept = DOC_SUMMARY_UPLOAD_ACCEPT
    for (const token of [
      '.doc',
      '.ppt',
      '.xls',
      '.xlsx',
      '.csv',
      '.txt',
      '.md',
      '.webp',
      'application/msword',
      'image/webp',
    ]) {
      expect(accept).toContain(token)
    }
  })
})

describe('isContentFilterDetail', () => {
  it('matches structured error_type from generate_mindmap_from_package', () => {
    expect(isContentFilterDetail({ error_type: 'content_filter', message: 'blocked' })).toBe(true)
  })

  it('matches leftover retry wrapper text', () => {
    expect(
      isContentFilterDetail(
        'All 3 attempts failed. Last error: Content filter: Input text data may contain inappropriate content.'
      )
    ).toBe(true)
  })

  it('matches Chinese safety-filter copy', () => {
    expect(isContentFilterDetail('输入可能包含不当内容，请修改输入内容')).toBe(true)
  })

  it('ignores other generate failures', () => {
    expect(isContentFilterDetail('Generation failed. Please try again.')).toBe(false)
    expect(isContentFilterDetail({ code: 'doc_summary_storage_conflict' })).toBe(false)
  })
})
