import { describe, expect, it } from 'vitest'

import {
  fileExtensionFromName,
  isMindmateComposerUploadableFile,
  isMindmateComposerWordFile,
  mindMateFileTypeFromMimeAndName,
} from '@/utils/mindmateComposerUpload'

describe('fileExtensionFromName', () => {
  it('returns lowercase extension', () => {
    expect(fileExtensionFromName('Lesson.DOCX')).toBe('docx')
    expect(fileExtensionFromName('notes.doc')).toBe('doc')
  })

  it('returns empty when missing or trailing-only', () => {
    expect(fileExtensionFromName('notes')).toBe('')
    expect(fileExtensionFromName('.hidden')).toBe('')
    expect(fileExtensionFromName('notes.')).toBe('')
  })
})

describe('isMindmateComposerWordFile', () => {
  it('accepts .doc and .docx by extension even with empty mime', () => {
    expect(isMindmateComposerWordFile({ name: 'plan.doc', type: '' })).toBe(true)
    expect(isMindmateComposerWordFile({ name: 'plan.docx', type: '' })).toBe(true)
  })

  it('accepts Word mime types', () => {
    expect(
      isMindmateComposerWordFile({
        name: 'plan',
        type: 'application/msword',
      })
    ).toBe(true)
    expect(
      isMindmateComposerWordFile({
        name: 'plan',
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
    ).toBe(true)
  })

  it('rejects other documents', () => {
    expect(isMindmateComposerWordFile({ name: 'notes.pdf', type: 'application/pdf' })).toBe(false)
    expect(isMindmateComposerWordFile({ name: 'photo.png', type: 'image/png' })).toBe(false)
  })
})

describe('isMindmateComposerUploadableFile', () => {
  it('allows images and Word documents', () => {
    expect(isMindmateComposerUploadableFile({ name: 'a.png', type: 'image/png' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.docx', type: '' })).toBe(true)
  })

  it('rejects pdf and spreadsheet from the paperclip', () => {
    expect(isMindmateComposerUploadableFile({ name: 'a.pdf', type: 'application/pdf' })).toBe(false)
    expect(
      isMindmateComposerUploadableFile({
        name: 'a.xlsx',
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
    ).toBe(false)
  })
})

describe('mindMateFileTypeFromMimeAndName', () => {
  it('maps Word mime and extension to document', () => {
    expect(mindMateFileTypeFromMimeAndName('application/msword', 'plan.doc')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('', 'plan.docx')).toBe('document')
  })

  it('keeps images as image', () => {
    expect(mindMateFileTypeFromMimeAndName('image/png', 'shot.png')).toBe('image')
  })
})
