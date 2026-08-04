import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  SHOWCASE_GALLERY_MAX_LONG_EDGE,
  isShowcaseGalleryAbortError,
  resizeImageFileForShowcaseGallery,
} from '@/composables/media/resizeImageFileForShowcaseGallery'

type FakeBitmap = {
  width: number
  height: number
  close: ReturnType<typeof vi.fn>
}

function installCanvasMock(blobFactory: (mime: string) => Blob | null): void {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
    return {
      fillStyle: '',
      fillRect: vi.fn(),
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D
  })
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function mockToBlob(
    callback: BlobCallback,
    type?: string,
    _quality?: number
  ) {
    const mime = type || 'image/png'
    queueMicrotask(() => callback(blobFactory(mime)))
  })
}

type CreateImageBitmapOptions = ImageBitmapOptions & {
  signal?: AbortSignal
}

function installBitmapMock(width: number, height: number): FakeBitmap {
  const bitmap: FakeBitmap = {
    width,
    height,
    close: vi.fn(),
  }
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async (_source: ImageBitmapSource, options?: CreateImageBitmapOptions) => {
      if (options?.signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError')
      }
      return bitmap as unknown as ImageBitmap
    })
  )
  return bitmap
}

describe('resizeImageFileForShowcaseGallery', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('leaves GIF files unchanged', async () => {
    const file = new File([new Uint8Array([0x47, 0x49, 0x46])], 'anim.gif', {
      type: 'image/gif',
    })
    await expect(resizeImageFileForShowcaseGallery(file)).resolves.toBe(file)
  })

  it('downscales oversized JPEG to JPEG within the long-edge budget', async () => {
    const bitmap = installBitmapMock(3200, 1800)
    installCanvasMock(
      (mime) => new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: mime })
    )

    const file = new File([new Uint8Array(40_000)], 'photo.jpeg', { type: 'image/jpeg' })
    const result = await resizeImageFileForShowcaseGallery(file)

    expect(result).not.toBe(file)
    expect(result.type).toBe('image/jpeg')
    expect(result.name).toBe('photo.jpg')
    expect(createImageBitmap).toHaveBeenCalledWith(
      file,
      expect.objectContaining({ imageOrientation: 'from-image' })
    )
    expect(bitmap.close).toHaveBeenCalled()

    const canvasCalls = vi.mocked(HTMLCanvasElement.prototype.toBlob).mock.instances
    expect(canvasCalls.length).toBeGreaterThan(0)
    const canvas = canvasCalls[0] as HTMLCanvasElement
    expect(Math.max(canvas.width, canvas.height)).toBe(SHOWCASE_GALLERY_MAX_LONG_EDGE)
  })

  it('keeps oversized PNG as PNG after re-encode', async () => {
    installBitmapMock(2000, 2000)
    installCanvasMock((mime) => new Blob([new Uint8Array([1, 2, 3, 4])], { type: mime }))

    const file = new File([new Uint8Array(20_000)], 'shot.png', { type: 'image/png' })
    const result = await resizeImageFileForShowcaseGallery(file)

    expect(result).not.toBe(file)
    expect(result.type).toBe('image/png')
    expect(result.name).toBe('shot.png')
  })

  it('re-encodes small JPEG so EXIF/GPS path is exercised even under the long-edge cap', async () => {
    installBitmapMock(800, 600)
    installCanvasMock(
      (mime) => new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0x00])], { type: mime })
    )

    const file = new File([new Uint8Array(12_000)], 'phone.jpg', { type: 'image/jpeg' })
    const result = await resizeImageFileForShowcaseGallery(file)

    expect(result).not.toBe(file)
    expect(result.type).toBe('image/jpeg')
    expect(result.name).toBe('phone.jpg')
    expect(createImageBitmap).toHaveBeenCalledWith(
      file,
      expect.objectContaining({ imageOrientation: 'from-image' })
    )
  })

  it('returns the original file when decode fails', async () => {
    vi.stubGlobal(
      'createImageBitmap',
      vi.fn(async () => {
        throw new Error('decode-fail')
      })
    )
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

    const file = new File([new Uint8Array(8000)], 'broken.jpg', { type: 'image/jpeg' })
    const result = await resizeImageFileForShowcaseGallery(file)
    expect(result).toBe(file)

    globalThis.Image = OriginalImage
    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
  })

  it('keeps original WebP when toBlob does not produce webp', async () => {
    installBitmapMock(1200, 900)
    installCanvasMock(() => new Blob([new Uint8Array([1, 2])], { type: 'image/png' }))

    const file = new File([new Uint8Array(9000)], 'pic.webp', { type: 'image/webp' })
    const result = await resizeImageFileForShowcaseGallery(file)
    expect(result).toBe(file)
  })

  it('throws AbortError when signal is already aborted', async () => {
    const controller = new AbortController()
    controller.abort()
    const file = new File([new Uint8Array(100)], 'a.jpg', { type: 'image/jpeg' })
    await expect(
      resizeImageFileForShowcaseGallery(file, { signal: controller.signal })
    ).rejects.toSatisfy(isShowcaseGalleryAbortError)
  })

  it('throws AbortError when aborted during encode', async () => {
    installBitmapMock(800, 600)
    const controller = new AbortController()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
      return {
        fillStyle: '',
        fillRect: vi.fn(),
        drawImage: vi.fn(),
      } as unknown as CanvasRenderingContext2D
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      controller.abort()
      queueMicrotask(() => callback(new Blob([new Uint8Array([1])], { type: 'image/jpeg' })))
    })

    const file = new File([new Uint8Array(4000)], 'late.jpg', { type: 'image/jpeg' })
    await expect(
      resizeImageFileForShowcaseGallery(file, { signal: controller.signal })
    ).rejects.toSatisfy(isShowcaseGalleryAbortError)
  })
})
