import { describe, expect, it } from 'vitest'

import {
  diagramSourceKindFromDocument,
  diagramSourceKindFromIngest,
  diagramSourceLockMessage,
  isDiagramSourceKindLocked,
  resolveLockedSourceKind,
} from '@/utils/diagramSourceKind'

describe('diagramSourceKindFromIngest', () => {
  it('maps known ingest families', () => {
    expect(diagramSourceKindFromIngest('web')).toBe('web')
    expect(diagramSourceKindFromIngest('voice_notes')).toBe('voice')
    expect(diagramSourceKindFromIngest('upload')).toBe('doc')
    expect(diagramSourceKindFromIngest('paste')).toBe('doc')
    expect(diagramSourceKindFromIngest('')).toBe(null)
    expect(diagramSourceKindFromIngest(undefined)).toBe(null)
  })
})

describe('diagramSourceKindFromDocument', () => {
  it('prefers ingest_source, then filename hints', () => {
    expect(diagramSourceKindFromDocument({ ingest_source: 'web', file_name: 'notes.pdf' })).toBe(
      'web'
    )
    expect(
      diagramSourceKindFromDocument({
        ingest_source: null,
        file_name: 'voice recording_202609141200.md',
      })
    ).toBe('voice')
    expect(
      diagramSourceKindFromDocument({ ingest_source: null, file_name: 'https://example.com/a' })
    ).toBe('web')
    expect(diagramSourceKindFromDocument({ file_name: 'lesson.pptx' })).toBe('doc')
  })
})

describe('resolveLockedSourceKind', () => {
  it('returns null when the package has no sources', () => {
    expect(resolveLockedSourceKind([])).toBe(null)
  })

  it('locks to the oldest source when voice notes are ingested later', () => {
    expect(
      resolveLockedSourceKind([
        {
          ingest_source: 'voice_notes',
          created_at: '2026-09-14T02:00:00',
          file_name: 'voice recording_20260914.md',
        },
        {
          ingest_source: 'upload',
          created_at: '2026-09-14T01:00:00',
          file_name: 'brief.pdf',
        },
      ])
    ).toBe('doc')
  })
})

describe('isDiagramSourceKindLocked', () => {
  it('allows the same family and blocks a switch', () => {
    expect(isDiagramSourceKindLocked(null, 'web')).toBe(false)
    expect(isDiagramSourceKindLocked('doc', 'doc')).toBe(false)
    expect(isDiagramSourceKindLocked('doc', 'voice')).toBe(true)
    expect(isDiagramSourceKindLocked('web', 'doc')).toBe(true)
  })
})

describe('diagramSourceLockMessage', () => {
  it('fills the locked-source notice', () => {
    const translate = (key: string, named?: Record<string, string>) => {
      if (key === 'canvas.ribbon.sourceKind.doc') return 'a document'
      if (key === 'canvas.ribbon.sourceLocked') {
        return `This diagram already uses ${named?.source}. Start a new diagram.`
      }
      return key
    }
    expect(diagramSourceLockMessage(translate, 'doc')).toBe(
      'This diagram already uses a document. Start a new diagram.'
    )
  })
})
