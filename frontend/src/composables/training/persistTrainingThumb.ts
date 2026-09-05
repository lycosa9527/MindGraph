import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'

export function isPersistedTrainingThumb(url: string | null | undefined): boolean {
  if (!url) return false
  return !url.startsWith('data:')
}

export async function dataUrlToPngFile(dataUrl: string, filename: string): Promise<File> {
  const response = await fetch(dataUrl)
  const blob = await response.blob()
  return new File([blob], filename, { type: 'image/png' })
}

export async function persistTrainingStageThumb(
  courseId: string,
  dataUrl: string,
  index: number
): Promise<{ id: string; url: string }> {
  const file = await dataUrlToPngFile(dataUrl, `slide-${index + 1}.png`)
  return uploadTrainingFile(courseId, 'thumb', file)
}
