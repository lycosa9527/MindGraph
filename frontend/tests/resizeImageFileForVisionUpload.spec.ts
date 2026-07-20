import { describe, expect, it, vi } from 'vitest'

import { resizeImageFileForVisionUpload } from '@/composables/media/resizeImageFileForVisionUpload'

describe('resizeImageFileForVisionUpload', () => {
  it('returns non-image files unchanged', async () => {
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    await expect(resizeImageFileForVisionUpload(file)).resolves.toBe(file)
  })

  it('returns the original file when decode fails', async () => {
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const OriginalImage = globalThis.Image
    class FailingImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      naturalWidth = 0
      naturalHeight = 0
      set src(_value: string) {
        queueMicrotask(() => this.onerror?.())
      }
    }
    // @ts-expect-error test stub
    globalThis.Image = FailingImage

    const file = new File([new Uint8Array(1200 * 1024)], 'big.jpg', { type: 'image/jpeg' })
    const result = await resizeImageFileForVisionUpload(file)
    expect(result).toBe(file)

    globalThis.Image = OriginalImage
    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
  })
})
