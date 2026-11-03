import { describe, expect, it } from 'vitest'

import { knowledgeProcessSnapshot, knowledgeProcessText } from '@/utils/knowledgeProcessStatus'

const labels: Record<string, string> = {
  'settings.knowledge.process.empty': 'No files yet',
  'settings.knowledge.process.pending': 'Pending',
  'settings.knowledge.process.queued': 'Queued',
  'settings.knowledge.process.extracting': 'Extracting text',
  'settings.knowledge.process.cleaning': 'Cleaning text',
  'settings.knowledge.process.splitting': 'Splitting files',
  'settings.knowledge.process.sending_oss': 'Uploading to OSS',
  'settings.knowledge.process.embedding': 'VibeFlow handoff',
  'settings.knowledge.process.ready': 'Ready',
  'settings.knowledge.process.failed': 'Failed',
  'settings.knowledge.process.working': 'Processing',
}

function translate(key: string, named?: Record<string, string | number>): string {
  if (key === 'settings.knowledge.process.withFile') {
    return `${named?.label} · ${named?.file}`
  }
  if (key === 'settings.knowledge.process.withCount') {
    return `${named?.label} · ${named?.count}`
  }
  return labels[key] ?? key
}

describe('knowledgeProcessSnapshot', () => {
  it('reports an empty folder', () => {
    expect(knowledgeProcessSnapshot([])).toEqual({ stage: 'empty', fileName: '', count: 0 })
  })

  it('follows the furthest file still running', () => {
    const snap = knowledgeProcessSnapshot([
      { status: 'pending', file_name: 'a.pdf', processing_progress: null },
      { status: 'processing', file_name: 'b.pdf', processing_progress: 'splitting' },
      { status: 'processing', file_name: 'c.pdf', processing_progress: 'sending_oss' },
    ])
    expect(snap).toEqual({ stage: 'sending_oss', fileName: '', count: 3 })
  })

  it('names the file when only one is running', () => {
    expect(
      knowledgeProcessText(
        [{ status: 'processing', file_name: 'notes.md', processing_progress: 'embedding' }],
        translate
      )
    ).toBe('VibeFlow handoff (7/7) · notes.md')
  })

  it('counts several files on the same live stage', () => {
    expect(
      knowledgeProcessText(
        [
          { status: 'processing', file_name: 'a.pdf', processing_progress: 'queued' },
          { status: 'processing', file_name: 'b.pdf', processing_progress: 'extracting' },
        ],
        translate
      )
    ).toBe('Extracting text (3/7) · 2')
  })

  it('starts the counter at pending', () => {
    expect(
      knowledgeProcessText(
        [{ status: 'pending', file_name: 'a.pdf', processing_progress: null }],
        translate
      )
    ).toBe('Pending (1/7) · a.pdf')
  })

  it('treats a processing row with no label as queued', () => {
    expect(
      knowledgeProcessText(
        [{ status: 'processing', file_name: 'a.pdf', processing_progress: null }],
        translate
      )
    ).toBe('Queued (2/7) · a.pdf')
  })

  it('does not let a waiting file hide an unrecognized running stage', () => {
    expect(
      knowledgeProcessText(
        [
          { status: 'processing', file_name: 'a.pdf', processing_progress: 'mystery' },
          { status: 'pending', file_name: 'b.pdf', processing_progress: null },
        ],
        translate
      )
    ).toBe('Processing · 2')
  })

  it('keeps a named stage ahead of an unrecognized one', () => {
    expect(
      knowledgeProcessText(
        [
          { status: 'processing', file_name: 'a.pdf', processing_progress: 'mystery' },
          { status: 'processing', file_name: 'b.pdf', processing_progress: 'splitting' },
        ],
        translate
      )
    ).toBe('Splitting files (5/7) · 2')
  })

  it('says ready only after every file finished', () => {
    expect(
      knowledgeProcessText(
        [{ status: 'completed', file_name: 'a.pdf', processing_progress: null }],
        translate
      )
    ).toBe('Ready')
  })

  it('names a single failure', () => {
    expect(
      knowledgeProcessText(
        [
          { status: 'completed', file_name: 'a.pdf', processing_progress: null },
          { status: 'failed', file_name: 'b.pdf', processing_progress: null },
        ],
        translate
      )
    ).toBe('Failed · b.pdf')
  })
})
