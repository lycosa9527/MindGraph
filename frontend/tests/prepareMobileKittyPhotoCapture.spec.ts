/**
 * Camera stub prepares compressed bytes but never implies Omni append_image send.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const compressMock = vi.hoisted(() => vi.fn(async () => 'base64-jpeg-data'))

vi.mock('@/composables/kitty/compressImageForKitty', () => ({
  compressImageFileForKitty: compressMock,
}))

import { prepareMobileKittyPhotoCapture } from '@/composables/mobile/prepareMobileKittyPhotoCapture'

describe('prepareMobileKittyPhotoCapture', () => {
  beforeEach(() => {
    compressMock.mockClear()
    compressMock.mockResolvedValue('base64-jpeg-data')
  })

  it('compresses a file for future OCR and does not require sendAppendImage', async () => {
    const file = new File(['x'], 'shot.jpg', { type: 'image/jpeg' })
    const result = await prepareMobileKittyPhotoCapture(file)
    expect(result).toEqual({ ok: true, compressedBase64: 'base64-jpeg-data' })
    expect(compressMock).toHaveBeenCalledWith(file)
  })

  it('returns no_file when input is empty', async () => {
    const result = await prepareMobileKittyPhotoCapture(null)
    expect(result).toEqual({ ok: false, reason: 'no_file' })
    expect(compressMock).not.toHaveBeenCalled()
  })

  it('returns compress_failed when compression throws', async () => {
    compressMock.mockRejectedValueOnce(new Error('boom'))
    const file = new File(['x'], 'shot.jpg', { type: 'image/jpeg' })
    const result = await prepareMobileKittyPhotoCapture(file)
    expect(result).toEqual({ ok: false, reason: 'compress_failed' })
  })
})
