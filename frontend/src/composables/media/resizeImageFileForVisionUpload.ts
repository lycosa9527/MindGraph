/**
 * Downscale camera / gallery photos before vision OCR / mind-map rebuild upload.
 * Keeps small images as-is; larger ones become JPEG within a long-edge budget.
 */

export const VISION_UPLOAD_MAX_LONG_EDGE = 1600
export const VISION_UPLOAD_JPEG_QUALITY = 0.85
/** Skip re-encode when already small enough on disk. */
export const VISION_UPLOAD_SKIP_BYTES = 900 * 1024

export type ResizeImageForVisionOptions = {
  maxLongEdge?: number
  jpegQuality?: number
  skipBelowBytes?: number
}

function extensionOf(fileName: string): string {
  const i = fileName.lastIndexOf('.')
  return i >= 0 ? fileName.slice(i).toLowerCase() : ''
}

function outputFileName(originalName: string): string {
  const base = originalName.replace(/\.[^.]+$/, '') || 'photo'
  return `${base}.jpg`
}

/**
 * Resize an image File for DashScope vision upload.
 * Returns the original File when already within budget or on decode failure.
 */
export async function resizeImageFileForVisionUpload(
  file: File,
  options: ResizeImageForVisionOptions = {}
): Promise<File> {
  const maxLongEdge = options.maxLongEdge ?? VISION_UPLOAD_MAX_LONG_EDGE
  const jpegQuality = options.jpegQuality ?? VISION_UPLOAD_JPEG_QUALITY
  const skipBelowBytes = options.skipBelowBytes ?? VISION_UPLOAD_SKIP_BYTES

  const mime = (file.type || '').toLowerCase()
  const isImage =
    mime.startsWith('image/') ||
    ['.jpg', '.jpeg', '.png', '.webp'].includes(extensionOf(file.name))
  if (!isImage) {
    return file
  }
  if (file.size > 0 && file.size <= skipBelowBytes) {
    // Still downscale very large dimensions even when file is compressed.
    // Decode below; if already within maxLongEdge, return original.
  }

  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('image-load'))
      img.src = url
    })
    const natW = img.naturalWidth || 0
    const natH = img.naturalHeight || 0
    if (natW < 1 || natH < 1) {
      return file
    }
    const curLong = Math.max(natW, natH)
    if (curLong <= maxLongEdge && file.size <= skipBelowBytes) {
      return file
    }

    let width = natW
    let height = natH
    if (curLong > maxLongEdge) {
      if (natW >= natH) {
        width = maxLongEdge
        height = Math.max(1, Math.round((natH * maxLongEdge) / natW))
      } else {
        height = maxLongEdge
        width = Math.max(1, Math.round((natW * maxLongEdge) / natH))
      }
    }

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return file
    }
    ctx.drawImage(img, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), 'image/jpeg', jpegQuality)
    })
    if (!blob || blob.size < 1) {
      return file
    }
    // Prefer the smaller payload; keep original when resize did not help.
    if (blob.size >= file.size && curLong <= maxLongEdge) {
      return file
    }
    return new File([blob], outputFileName(file.name), {
      type: 'image/jpeg',
      lastModified: Date.now(),
    })
  } catch {
    return file
  } finally {
    URL.revokeObjectURL(url)
  }
}
