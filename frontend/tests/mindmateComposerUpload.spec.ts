import { describe, expect, it } from 'vitest'

import {
  MINDMATE_COMPOSER_FILE_ACCEPT,
  difyUploadMaxBytes,
  fileExtensionFromName,
  isDifyGatewayUploadableFile,
  isMindmateBlockedDocUpload,
  isMindmateComposerDocumentFile,
  isMindmateComposerUploadableFile,
  isMindmateComposerWordFile,
  isMindmateLegacyDocFile,
  mindMateFileTypeFromMimeAndName,
  parseDifyUploadErrorDetail,
  resolveDifyChatFileType,
} from '@/utils/mindmateComposerUpload'

describe('MINDMATE_COMPOSER_FILE_ACCEPT', () => {
  it('includes Word (.docx), PDF, and PowerPoint in the file picker', () => {
    const parts = MINDMATE_COMPOSER_FILE_ACCEPT.split(',')
    expect(parts).toContain('.docx')
    expect(parts).toContain('.pdf')
    expect(parts).toContain('.ppt')
    expect(parts).toContain('.pptx')
    expect(parts).toContain('image/*')
    expect(parts).not.toContain('.doc')
    expect(parts).not.toContain('application/msword')
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

describe('isMindmateLegacyDocFile', () => {
  it('detects .doc by extension and legacy Word mime', () => {
    expect(isMindmateLegacyDocFile({ name: 'plan.doc', type: '' })).toBe(true)
    expect(isMindmateLegacyDocFile({ name: 'plan.DOC', type: '' })).toBe(true)
    expect(isMindmateLegacyDocFile({ name: 'plan', type: 'application/msword' })).toBe(true)
  })

  it('keeps .docx even when the mime is mislabeled as legacy Word', () => {
    expect(isMindmateLegacyDocFile({ name: 'plan.docx', type: 'application/msword' })).toBe(false)
    expect(isMindmateLegacyDocFile({ name: 'notes.pdf', type: 'application/pdf' })).toBe(false)
  })
})

describe('isMindmateBlockedDocUpload', () => {
  it('blocks a .doc renamed to .docx when the bytes are still OLE', async () => {
    const bytes = new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0, 0])
    const renamed = new File([bytes], 'plan.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const realDocx = new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], 'plan.docx')
    const slides = new File([bytes], 'deck.ppt')

    expect(await isMindmateBlockedDocUpload(renamed)).toBe(true)
    expect(await isMindmateBlockedDocUpload(realDocx)).toBe(false)
    expect(await isMindmateBlockedDocUpload(slides)).toBe(false)
    expect(await isMindmateBlockedDocUpload(new File([bytes], 'plan.doc'))).toBe(true)
  })
})

describe('isMindmateComposerWordFile', () => {
  it('accepts .docx by extension even with empty mime', () => {
    expect(isMindmateComposerWordFile({ name: 'plan.doc', type: '' })).toBe(false)
    expect(isMindmateComposerWordFile({ name: 'plan.docx', type: '' })).toBe(true)
  })

  it('accepts the .docx mime type', () => {
    expect(
      isMindmateComposerWordFile({
        name: 'plan',
        type: 'application/msword',
      })
    ).toBe(false)
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
  it('accepts Word (.docx), PDF, and PowerPoint by extension with empty mime', () => {
    expect(isMindmateComposerDocumentFile({ name: 'plan.doc', type: '' })).toBe(false)
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

  it('rejects legacy .doc from the paperclip', () => {
    expect(isMindmateComposerUploadableFile({ name: 'a.doc', type: '' })).toBe(false)
    expect(isMindmateComposerUploadableFile({ name: 'a', type: 'application/msword' })).toBe(false)
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
