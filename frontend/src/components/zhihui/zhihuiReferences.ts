/**
 * Client-side reference images for ZhiHui I2I (Qwen multimodal).
 */

export const ZHIHUI_MAX_REFERENCE_IMAGES = 3
export const ZHIHUI_MAX_REFERENCE_BYTES = 4 * 1024 * 1024

export type ZhihuiReferenceImage = {
  id: string
  name: string
  mime: string
  dataUrl: string
}

const ALLOWED_MIME = new Set(['image/png', 'image/jpeg', 'image/jpg', 'image/webp'])

export function isAllowedReferenceMime(mime: string): boolean {
  return ALLOWED_MIME.has((mime || '').toLowerCase())
}

export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      if (typeof result === 'string' && result.startsWith('data:image/')) {
        resolve(result)
        return
      }
      reject(new Error('invalid image data'))
    }
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsDataURL(file)
  })
}
