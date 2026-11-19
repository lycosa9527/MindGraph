import { beforeEach, describe, expect, it, vi } from 'vitest'

import { processConversationImageUpload } from '@/composables/kitty/processConversationImageUpload'

const apiUpload = vi.fn()
const resizeImageFileForVisionUpload = vi.fn()

vi.mock('@/utils/apiClient', () => ({
  apiUpload: (...args: unknown[]) => apiUpload(...args),
}))

vi.mock('@/composables/media/resizeImageFileForVisionUpload', () => ({
  resizeImageFileForVisionUpload: (...args: unknown[]) => resizeImageFileForVisionUpload(...args),
}))

vi.mock('@/composables/mindMap/audience/withMindMapAudienceContext', () => ({
  appendMindMapAudienceFormField: () => undefined,
}))

describe('processConversationImageUpload', () => {
  beforeEach(() => {
    apiUpload.mockReset()
    resizeImageFileForVisionUpload.mockReset()
    resizeImageFileForVisionUpload.mockImplementation(async (file: File) => file)
  })

  it('posts resized image and maps handdrawn result', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'map.jpg', {
      type: 'image/jpeg',
    })
    apiUpload.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        mode: 'handdrawn',
        is_mindmap: true,
        topic: 'Trees',
        package_id: 9,
        doc_summary_saved: true,
        spec: { topic: 'Trees', children: [] },
        library: { saved: true, desktop_queued: true },
      }),
    })

    const result = await processConversationImageUpload({
      file,
      diagramId: 'diag-1',
      diagramTitle: 'My Map',
      language: 'en',
    })

    expect(resizeImageFileForVisionUpload).toHaveBeenCalledWith(file)
    expect(apiUpload).toHaveBeenCalledWith('/api/kitty/conversation_image', expect.any(FormData))
    const form = apiUpload.mock.calls[0][1] as FormData
    expect(form.get('diagram_id')).toBe('diag-1')
    expect(form.get('diagram_title')).toBe('My Map')
    expect(form.get('language')).toBe('en')
    expect(result.mode).toBe('handdrawn')
    expect(result.topic).toBe('Trees')
    expect(result.docSummarySaved).toBe(true)
    expect(result.appliedToLibrary).toBe(true)
    expect(result.desktopQueued).toBe(true)
  })

  it('maps OCR text mode', async () => {
    const file = new File([new Uint8Array([1])], 'notes.png', { type: 'image/png' })
    apiUpload.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        mode: 'text',
        is_mindmap: false,
        ocr_excerpt: 'Hello',
        ocr_text: 'Hello world',
        package_id: 3,
      }),
    })

    const result = await processConversationImageUpload({
      file,
      diagramId: 'diag-2',
    })

    expect(result.mode).toBe('text')
    expect(result.ocrExcerpt).toBe('Hello')
    expect(result.packageId).toBe(3)
  })

  it('allows canvas-only upload without diagram id', async () => {
    const file = new File([new Uint8Array([1])], 'map.jpg', { type: 'image/jpeg' })
    apiUpload.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        mode: 'handdrawn',
        is_mindmap: true,
        topic: 'Sky',
        spec: { topic: 'Sky', children: [{ text: 'Cloud' }] },
        doc_summary_saved: false,
        library: {},
      }),
    })

    const result = await processConversationImageUpload({
      file,
      language: 'zh',
      applyToLibrary: false,
    })

    const form = apiUpload.mock.calls[0][1] as FormData
    expect(form.get('diagram_id')).toBe('')
    expect(form.get('apply_to_library')).toBe('false')
    expect(result.mode).toBe('handdrawn')
    expect(result.topic).toBe('Sky')
    expect(result.docSummarySaved).toBe(false)
    expect(result.appliedToLibrary).toBe(false)
  })
})
