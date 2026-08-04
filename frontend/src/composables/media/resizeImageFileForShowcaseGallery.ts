/**
 * Downscale showcase gallery images and strip EXIF/GPS via canvas re-encode.
 * Preserves PNG / JPEG / WebP; leaves GIF unchanged (animation).
 */

export const SHOWCASE_GALLERY_MAX_LONG_EDGE = 1600
export const SHOWCASE_GALLERY_JPEG_QUALITY = 0.85
export const SHOWCASE_GALLERY_WEBP_QUALITY = 0.85

type OutputFormat = {
  mime: 'image/png' | 'image/jpeg' | 'image/webp'
  extension: '.png' | '.jpg' | '.webp'
  quality?: number
}

export type ResizeShowcaseGalleryOptions = {
  maxLongEdge?: number
  signal?: AbortSignal
}

/** DOM lib lags the HTML ImageBitmapOptions.signal field; keep runtime abort wired. */
type CreateImageBitmapOptions = ImageBitmapOptions & {
  signal?: AbortSignal
}

function abortError(): DOMException {
  return new DOMException('Aborted', 'AbortError')
}

export function isShowcaseGalleryAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw abortError()
  }
}

function extensionOf(fileName: string): string {
  const i = fileName.lastIndexOf('.')
  return i >= 0 ? fileName.slice(i).toLowerCase() : ''
}

function resolveOutputFormat(file: File): OutputFormat | null {
  const ext = extensionOf(file.name)
  const mime = (file.type || '').toLowerCase()

  if (ext === '.gif' || mime === 'image/gif') {
    return null
  }
  if (ext === '.png' || mime === 'image/png') {
    return { mime: 'image/png', extension: '.png' }
  }
  if (ext === '.webp' || mime === 'image/webp') {
    return { mime: 'image/webp', extension: '.webp', quality: SHOWCASE_GALLERY_WEBP_QUALITY }
  }
  if (
    ext === '.jpg' ||
    ext === '.jpeg' ||
    mime === 'image/jpeg' ||
    mime === 'image/jpg'
  ) {
    return { mime: 'image/jpeg', extension: '.jpg', quality: SHOWCASE_GALLERY_JPEG_QUALITY }
  }
  if (mime.startsWith('image/')) {
    return { mime: 'image/jpeg', extension: '.jpg', quality: SHOWCASE_GALLERY_JPEG_QUALITY }
  }
  return null
}

function outputFileName(originalName: string, extension: OutputFormat['extension']): string {
  const base = originalName.replace(/\.[^.]+$/, '') || 'gallery'
  return `${base}${extension}`
}

function scaledSize(
  natW: number,
  natH: number,
  maxLongEdge: number
): { width: number; height: number } {
  const curLong = Math.max(natW, natH)
  if (curLong <= maxLongEdge) {
    return { width: natW, height: natH }
  }
  if (natW >= natH) {
    return {
      width: maxLongEdge,
      height: Math.max(1, Math.round((natH * maxLongEdge) / natW)),
    }
  }
  return {
    height: maxLongEdge,
    width: Math.max(1, Math.round((natW * maxLongEdge) / natH)),
  }
}

async function decodeImageBitmap(
  file: File,
  signal?: AbortSignal
): Promise<ImageBitmap | null> {
  if (typeof createImageBitmap !== 'function') {
    return null
  }
  throwIfAborted(signal)
  const orientedOptions: CreateImageBitmapOptions = signal
    ? { imageOrientation: 'from-image', signal }
    : { imageOrientation: 'from-image' }
  try {
    return await createImageBitmap(file, orientedOptions)
  } catch (error) {
    if (isShowcaseGalleryAbortError(error) || signal?.aborted) {
      throw abortError()
    }
    try {
      throwIfAborted(signal)
      const fallbackOptions: CreateImageBitmapOptions | undefined = signal
        ? { signal }
        : undefined
      return fallbackOptions
        ? await createImageBitmap(file, fallbackOptions)
        : await createImageBitmap(file)
    } catch (fallbackError) {
      if (isShowcaseGalleryAbortError(fallbackError) || signal?.aborted) {
        throw abortError()
      }
      return null
    }
  }
}

type DecodedImageElement = {
  width: number
  height: number
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void
  cleanup: () => void
}

async function decodeViaImageElement(
  file: File,
  signal?: AbortSignal
): Promise<DecodedImageElement | null> {
  throwIfAborted(signal)
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      const onAbort = () => {
        cleanupListeners()
        reject(abortError())
      }
      const cleanupListeners = () => {
        signal?.removeEventListener('abort', onAbort)
        img.onload = null
        img.onerror = null
      }
      img.onload = () => {
        cleanupListeners()
        resolve()
      }
      img.onerror = () => {
        cleanupListeners()
        reject(new Error('image-load'))
      }
      signal?.addEventListener('abort', onAbort, { once: true })
      img.src = url
    })
    throwIfAborted(signal)
    const width = img.naturalWidth || 0
    const height = img.naturalHeight || 0
    if (width < 1 || height < 1) {
      URL.revokeObjectURL(url)
      return null
    }
    return {
      width,
      height,
      draw: (ctx, w, h) => {
        ctx.drawImage(img, 0, 0, w, h)
      },
      cleanup: () => {
        URL.revokeObjectURL(url)
      },
    }
  } catch (error) {
    URL.revokeObjectURL(url)
    if (isShowcaseGalleryAbortError(error) || signal?.aborted) {
      throw abortError()
    }
    return null
  }
}

function canvasToBlob(
  canvas: HTMLCanvasElement,
  format: OutputFormat,
  signal?: AbortSignal
): Promise<Blob | null> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    const onAbort = () => {
      signal?.removeEventListener('abort', onAbort)
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbort, { once: true })
    const finish = (blob: Blob | null) => {
      signal?.removeEventListener('abort', onAbort)
      if (signal?.aborted) {
        reject(abortError())
        return
      }
      resolve(blob)
    }
    if (format.quality !== undefined) {
      canvas.toBlob((blob) => finish(blob), format.mime, format.quality)
      return
    }
    canvas.toBlob((blob) => finish(blob), format.mime)
  })
}

async function encodeCanvasFile(
  file: File,
  format: OutputFormat,
  natW: number,
  natH: number,
  maxLongEdge: number,
  draw: (ctx: CanvasRenderingContext2D, width: number, height: number) => void,
  signal?: AbortSignal
): Promise<File | null> {
  throwIfAborted(signal)
  if (natW < 1 || natH < 1) {
    return null
  }
  const { width, height } = scaledSize(natW, natH, maxLongEdge)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return null
  }
  if (format.mime === 'image/jpeg') {
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
  }
  draw(ctx, width, height)
  throwIfAborted(signal)
  const blob = await canvasToBlob(canvas, format, signal)
  throwIfAborted(signal)
  if (!blob || blob.size < 1) {
    return null
  }
  if (format.mime === 'image/webp' && blob.type && !blob.type.includes('webp')) {
    return null
  }
  return new File([blob], outputFileName(file.name, format.extension), {
    type: format.mime,
    lastModified: Date.now(),
  })
}

/**
 * Re-encode a gallery image for showcase upload: strip EXIF/GPS, cap long edge.
 * Returns the original File for GIF, non-images, or soft-fail decode/encode errors.
 * Throws AbortError when `signal` is aborted.
 */
export async function resizeImageFileForShowcaseGallery(
  file: File,
  options: ResizeShowcaseGalleryOptions = {}
): Promise<File> {
  const maxLongEdge = options.maxLongEdge ?? SHOWCASE_GALLERY_MAX_LONG_EDGE
  const { signal } = options
  throwIfAborted(signal)

  const format = resolveOutputFormat(file)
  if (!format) {
    return file
  }

  try {
    const bitmap = await decodeImageBitmap(file, signal)
    if (bitmap) {
      try {
        const encoded = await encodeCanvasFile(
          file,
          format,
          bitmap.width,
          bitmap.height,
          maxLongEdge,
          (ctx, width, height) => {
            ctx.drawImage(bitmap, 0, 0, width, height)
          },
          signal
        )
        return encoded ?? file
      } finally {
        bitmap.close()
      }
    }

    const decoded = await decodeViaImageElement(file, signal)
    if (!decoded) {
      return file
    }
    try {
      const encoded = await encodeCanvasFile(
        file,
        format,
        decoded.width,
        decoded.height,
        maxLongEdge,
        decoded.draw,
        signal
      )
      return encoded ?? file
    } finally {
      decoded.cleanup()
    }
  } catch (error) {
    if (isShowcaseGalleryAbortError(error) || signal?.aborted) {
      throw abortError()
    }
    return file
  }
}
