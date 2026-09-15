import { afterEach, describe, expect, it, vi } from 'vitest'

import { authFetch } from '@/utils/api'
import {
  downloadTeachingDesignDocx,
  filenameFromDisposition,
  TeachingDesignExportError,
  teachingDesignExportFailI18nKey,
} from '@/utils/exportTeachingDesignDocx'

vi.mock('@/utils/api', () => ({
  authFetch: vi.fn(),
}))

const authFetchMock = vi.mocked(authFetch)

function jsonErrorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('exportTeachingDesignDocx', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    authFetchMock.mockReset()
  })

  it('reads RFC 5987 filenames from Content-Disposition', () => {
    expect(
      filenameFromDisposition("attachment; filename=\"lesson.docx\"; filename*=UTF-8''%E6%95%99%E5%AD%A6%E8%AE%BE%E8%AE%A1.docx")
    ).toBe('教学设计.docx')
    expect(filenameFromDisposition(null)).toBe('教学设计.docx')
  })

  it('maps API failures to user-facing i18n keys', () => {
    expect(
      teachingDesignExportFailI18nKey(
        new TeachingDesignExportError('not_flagged', 400, 'teaching_design_not_flagged')
      )
    ).toBe('mindmate.exportWordTemplateFailNotFlagged')
    expect(
      teachingDesignExportFailI18nKey(
        new TeachingDesignExportError('too_large', 413, 'teaching_design_too_large')
      )
    ).toBe('mindmate.exportWordTemplateFailTooLarge')
    expect(
      teachingDesignExportFailI18nKey(new TeachingDesignExportError('network', 0, 'offline'))
    ).toBe('mindmate.exportWordTemplateFailNetwork')
    expect(
      teachingDesignExportFailI18nKey(new TeachingDesignExportError('server', 500, 'boom'))
    ).toBe('mindmate.exportWordTemplateFailServer')
  })

  it('throws a typed error for flagged API detail codes', async () => {
    authFetchMock.mockResolvedValue(jsonErrorResponse(400, 'teaching_design_not_flagged'))
    await expect(
      downloadTeachingDesignDocx({
        assistantMarkdown: '课例\n<!-- mg-reply-kind:teaching_instruction -->',
      })
    ).rejects.toMatchObject({
      name: 'TeachingDesignExportError',
      code: 'not_flagged',
      status: 400,
    })
  })

  it('throws a network error when the request cannot be sent', async () => {
    authFetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(
      downloadTeachingDesignDocx({
        assistantMarkdown: '课例\n<!-- mg-reply-kind:teaching_instruction -->',
      })
    ).rejects.toMatchObject({
      code: 'network',
    })
  })

  it('appends a download link so the file still saves after leaving MindMate', async () => {
    const blob = new Blob(['PK'], { type: 'application/octet-stream' })
    authFetchMock.mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: {
          'Content-Disposition': 'attachment; filename="lesson.docx"',
        },
      })
    )
    const createObjectURL = vi.fn(() => 'blob:teaching-design')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.fn()
    const originalCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const element = originalCreate(tagName)
      if (tagName === 'a') {
        element.click = click
      }
      return element
    })

    await downloadTeachingDesignDocx({
      assistantMarkdown: '课例\n<!-- mg-reply-kind:teaching_instruction -->',
    })

    expect(click).toHaveBeenCalled()
    expect(document.body.querySelector('a')).toBeNull()
  })
})
