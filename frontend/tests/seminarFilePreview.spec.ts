import { describe, expect, it } from 'vitest'

import {
  seminarFilePreviewMode,
  seminarPreviewFromResponse,
} from '@/utils/mindmateSeminarFolder'

describe('seminarFilePreviewMode', () => {
  it('treats Word uploads as office preview', () => {
    expect(
      seminarFilePreviewMode(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '从新服务器中部署MindGraph.docx'
      )
    ).toBe('office')
  })
})

describe('seminarPreviewFromResponse', () => {
  it('reads extracted Office text when LibreOffice is unavailable', () => {
    const encoded = new TextEncoder().encode('研讨资源正文')
    expect(seminarPreviewFromResponse('text/plain; charset=utf-8', encoded)).toEqual({
      kind: 'text',
      text: '研讨资源正文',
    })
  })

  it('keeps converted PDF bytes for pdf.js', () => {
    const data = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])
    expect(seminarPreviewFromResponse('application/pdf', data)).toEqual({
      kind: 'pdf',
      data,
    })
  })
})
