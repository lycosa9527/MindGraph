import { describe, expect, it } from 'vitest'

import {
  MINDMATE_COMPOSER_FILE_ACCEPT,
  difyUploadMaxBytes,
  fileExtensionFromName,
  isDifyGatewayUploadableFile,
  isMindmateComposerDocumentFile,
  isMindmateComposerUploadableFile,
  isMindmateComposerWordFile,
  mindMateFileTypeFromMimeAndName,
  parseDifyUploadErrorDetail,
  resolveDifyChatFileType,
} from '@/utils/mindmateComposerUpload'

describe('MINDMATE_COMPOSER_FILE_ACCEPT', () => {
  it('includes Word, PDF, and PowerPoint in the file picker', () => {
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('.doc')
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('.docx')
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('.pdf')
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('.ppt')
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('.pptx')
    expect(MINDMATE_COMPOSER_FILE_ACCEPT).toContain('image/*')
  })
})

describe('fileExtensionFromName', () => {
  it('returns lowercase extension', () => {
    expect(fileExtensionFromName('Lesson.DOCX')).toBe('docx')
    expect(fileExtensionFromName('notes.doc')).toBe('doc')
    expect(fileExtensionFromName('slides.PPTX')).toBe('pptx')
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
    expect(isMindmateComposerWordFile({ name: 'deck.ppt', type: '' })).toBe(false)
    expect(isMindmateComposerWordFile({ name: 'photo.png', type: 'image/png' })).toBe(false)
  })
})

describe('isMindmateComposerDocumentFile', () => {
  it('accepts Word, PDF, and PowerPoint by extension with empty mime', () => {
    expect(isMindmateComposerDocumentFile({ name: 'plan.doc', type: '' })).toBe(true)
    expect(isMindmateComposerDocumentFile({ name: 'plan.docx', type: '' })).toBe(true)
    expect(isMindmateComposerDocumentFile({ name: 'notes.pdf', type: '' })).toBe(true)
    expect(isMindmateComposerDocumentFile({ name: 'deck.ppt', type: '' })).toBe(true)
    expect(isMindmateComposerDocumentFile({ name: 'deck.pptx', type: '' })).toBe(true)
  })

  it('accepts PDF and PowerPoint mime types', () => {
    expect(isMindmateComposerDocumentFile({ name: 'notes', type: 'application/pdf' })).toBe(true)
    expect(
      isMindmateComposerDocumentFile({
        name: 'deck',
        type: 'application/vnd.ms-powerpoint',
      })
    ).toBe(true)
    expect(
      isMindmateComposerDocumentFile({
        name: 'deck',
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      })
    ).toBe(true)
  })

  it('rejects spreadsheets and images', () => {
    expect(
      isMindmateComposerDocumentFile({
        name: 'sheet.xlsx',
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
    ).toBe(false)
    expect(isMindmateComposerDocumentFile({ name: 'photo.png', type: 'image/png' })).toBe(false)
  })
})

describe('isMindmateComposerUploadableFile', () => {
  it('allows images, Word, PDF, and PowerPoint', () => {
    expect(isMindmateComposerUploadableFile({ name: 'a.png', type: 'image/png' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.png', type: '' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.docx', type: '' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.pdf', type: 'application/pdf' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.ppt', type: '' })).toBe(true)
    expect(isMindmateComposerUploadableFile({ name: 'a.pptx', type: '' })).toBe(true)
  })

  it('rejects spreadsheet from the paperclip', () => {
    expect(
      isMindmateComposerUploadableFile({
        name: 'a.xlsx',
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
    ).toBe(false)
  })
})

describe('mindMateFileTypeFromMimeAndName', () => {
  it('uses Dify extension-first mapping for Word, PDF, and PowerPoint', () => {
    expect(mindMateFileTypeFromMimeAndName('application/msword', 'plan.doc')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('', 'plan.docx')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('application/pdf', 'notes.pdf')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('', 'notes.pdf')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('', 'deck.ppt')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('', 'deck.pptx')).toBe('document')
  })

  it('classifies images from extension even when mime is empty', () => {
    expect(mindMateFileTypeFromMimeAndName('', 'shot.png')).toBe('image')
    expect(mindMateFileTypeFromMimeAndName('image/png', 'shot.png')).toBe('image')
  })

  it('falls back to Dify MIME rules when the name has no known extension', () => {
    expect(mindMateFileTypeFromMimeAndName('application/pdf', 'notes')).toBe('document')
    expect(mindMateFileTypeFromMimeAndName('application/msword', 'plan')).toBe('custom')
    expect(mindMateFileTypeFromMimeAndName('image/jpeg', 'photo')).toBe('image')
  })
})

describe('resolveDifyChatFileType', () => {
  it('prefers the upload API type when it is a Dify chat file type', () => {
    expect(resolveDifyChatFileType('document', 'image/png', 'shot.png')).toBe('document')
    expect(resolveDifyChatFileType('IMAGE', '', 'shot.png')).toBe('image')
  })

  it('falls back to local Dify mapping when the API type is missing', () => {
    expect(resolveDifyChatFileType(undefined, '', 'deck.pptx')).toBe('document')
  })
})

describe('isDifyGatewayUploadableFile', () => {
  it('accepts Dify document extras used by Showcase', () => {
    expect(isDifyGatewayUploadableFile({ name: 'sheet.xlsx', type: '' })).toBe(true)
    expect(isDifyGatewayUploadableFile({ name: 'notes.md', type: '' })).toBe(true)
  })

  it('rejects unknown extensions without a media mime', () => {
    expect(isDifyGatewayUploadableFile({ name: 'virus.exe', type: '' })).toBe(false)
  })
})

describe('difyUploadMaxBytes', () => {
  it('uses Dify default caps', () => {
    expect(difyUploadMaxBytes('shot.png')).toBe(10 * 1024 * 1024)
    expect(difyUploadMaxBytes('notes.pdf')).toBe(15 * 1024 * 1024)
    expect(difyUploadMaxBytes('deck.pptx')).toBe(15 * 1024 * 1024)
  })
})

describe('parseDifyUploadErrorDetail', () => {
  it('reads string and FastAPI validation details', () => {
    expect(parseDifyUploadErrorDetail({ detail: 'File too large' })).toBe('File too large')
    expect(parseDifyUploadErrorDetail({ detail: [{ msg: 'type must be one of: document' }] })).toBe(
      'type must be one of: document'
    )
    expect(parseDifyUploadErrorDetail({})).toBe('Upload failed')
  })
})
