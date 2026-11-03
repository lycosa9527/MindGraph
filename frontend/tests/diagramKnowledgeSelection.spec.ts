import { describe, expect, it } from 'vitest'

import { knowledgeButtonOn, nextKnowledgeFolderId } from '@/utils/diagramKnowledgeSelection'
import { documentWorkTone, folderIsReady, folderWorkTone } from '@/utils/knowledgeWorkTone'

describe('diagram knowledge selection', () => {
  it('leaves a new diagram with no folder', () => {
    expect(knowledgeButtonOn(null, true)).toBe(false)
    expect(nextKnowledgeFolderId(null, 1, false)).toBeNull()
  })

  it('replaces the previous folder and clears it on a second click', () => {
    expect(nextKnowledgeFolderId(null, 1, true)).toBe(1)
    expect(nextKnowledgeFolderId(1, 2, true)).toBe(2)
    expect(nextKnowledgeFolderId(2, 2, true)).toBeNull()
    expect(knowledgeButtonOn(2, true)).toBe(true)
  })

  it('does not activate a folder until every file has finished', () => {
    expect(nextKnowledgeFolderId(1, 9, false)).toBe(1)
    expect(knowledgeButtonOn(9, false)).toBe(false)
  })
})

describe('knowledge work tone', () => {
  it('colors a file by its stored status', () => {
    expect(documentWorkTone('pending')).toBe('working')
    expect(documentWorkTone('processing')).toBe('working')
    expect(documentWorkTone('failed')).toBe('failed')
    expect(documentWorkTone('completed')).toBe('ready')
  })

  it('keeps a folder off until every document has finished', () => {
    expect(folderWorkTone({ document_count: 0, completed_count: 0 })).toBe('idle')
    expect(
      folderWorkTone({
        document_count: 2,
        completed_count: 1,
        processing_count: 1,
        failed_count: 0,
      })
    ).toBe('working')
    expect(
      folderWorkTone({
        document_count: 2,
        completed_count: 1,
        processing_count: 0,
        failed_count: 1,
      })
    ).toBe('failed')
    const ready = { document_count: 2, completed_count: 2, processing_count: 0, failed_count: 0 }
    expect(folderWorkTone(ready)).toBe('ready')
    expect(folderIsReady(ready)).toBe(true)
    expect(folderIsReady({ document_count: 2, completed_count: 1, processing_count: 1 })).toBe(
      false
    )
  })
})
