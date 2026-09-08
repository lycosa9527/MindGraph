import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'

export function isPersistedTrainingThumb(url: string | null | undefined): boolean {
  if (!url) return false
  return !url.startsWith('data:')
}

function decodeDataUrlBytes(dataUrl: string): ArrayBuffer {
  const comma = dataUrl.indexOf(',')
  if (comma < 0) {
    throw new Error('invalid data url')
  }
  const header = dataUrl.slice(0, comma)
  const payload = dataUrl.slice(comma + 1)
  const binary = /;base64/i.test(header) ? atob(payload) : decodeURIComponent(payload)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
}

export function dataUrlToPngFile(dataUrl: string, filename: string): File {
  return new File([decodeDataUrlBytes(dataUrl)], filename, { type: 'image/png' })
}

export async function persistTrainingStageThumb(
  courseId: string,
  dataUrl: string,
  index: number
): Promise<{ id: string; url: string }> {
  const file = dataUrlToPngFile(dataUrl, `slide-${index + 1}.png`)
  return uploadTrainingFile(courseId, 'thumb', file)
}
