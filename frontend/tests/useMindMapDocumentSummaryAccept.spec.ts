import { describe, expect, it } from 'vitest'

import { DOC_SUMMARY_UPLOAD_ACCEPT } from '@/composables/mindMap/useMindMapDocumentSummary'

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
