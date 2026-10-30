import { describe, expect, it } from 'vitest'

import {
  type SeminarBackgroundFile,
  rememberSeminarBackgroundFile,
  seminarLiveFilename,
  seminarRenameFilename,
} from '@/utils/mindmateSeminarFolder'

function shelfFile(id: string, filename: string): SeminarBackgroundFile {
  return {
    id,
    filename,
    contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    sizeBytes: 1,
    uploaderName: '',
    pinned: false,
    pinnedAt: null,
    createdAt: '2026-10-30T00:00:00.000Z',
    sourceMessageId: null,
    listed: false,
    artifact: true,
    kind: '',
    diagramId: null,
  }
}

describe('seminarRenameFilename', () => {
  it('puts the original extension back when the new title omits it', () => {
    expect(seminarRenameFilename('一-核心迷思概念识别.docx', '核心概念')).toBe('核心概念.docx')
  })

  it('keeps a name that already uses the same extension', () => {
    expect(seminarRenameFilename('一-核心迷思概念识别.docx', '核心概念.docx')).toBe('核心概念.docx')
  })

  it('does not switch the file to another extension', () => {
    expect(seminarRenameFilename('notes.docx', 'notes.pdf')).toBe('notes.docx')
  })
})

describe('seminarLiveFilename', () => {
  it('uses the renamed shelf name in place of the chat token', () => {
    rememberSeminarBackgroundFile('session-1', shelfFile('file-1', '核心概念.docx'))
    expect(seminarLiveFilename('session-1', 'file-1', '一-核心迷思概念识别.docx')).toBe(
      '核心概念.docx'
    )
  })

  it('keeps the chat token until a rename is stored', () => {
    expect(seminarLiveFilename('session-1', 'missing', '一-核心迷思概念识别.docx')).toBe(
      '一-核心迷思概念识别.docx'
    )
  })
})
