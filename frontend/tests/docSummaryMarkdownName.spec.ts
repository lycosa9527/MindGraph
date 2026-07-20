import { describe, expect, it } from 'vitest'

import {
  docSummarySourceLabel,
  toDocSummaryMarkdownName,
} from '@/utils/docSummaryMarkdownName'

describe('toDocSummaryMarkdownName', () => {
  it('turns office/pdf names into .md', () => {
    expect(toDocSummaryMarkdownName('期末复习.pptx')).toBe('期末复习.md')
    expect(toDocSummaryMarkdownName('report.PDF')).toBe('report.md')
    expect(toDocSummaryMarkdownName('notes.docx')).toBe('notes.md')
  })

  it('keeps already-md names', () => {
    expect(toDocSummaryMarkdownName('outline.md')).toBe('outline.md')
  })

  it('falls back when empty', () => {
    expect(toDocSummaryMarkdownName('')).toBe('document.md')
    expect(toDocSummaryMarkdownName(null)).toBe('document.md')
  })
})

describe('docSummarySourceLabel', () => {
  it('returns the basename', () => {
    expect(docSummarySourceLabel('folder/deck.ppt')).toBe('deck.ppt')
  })
})
