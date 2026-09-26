/**
 * Hand an exported file to the user.
 * Phones open the system share sheet (WeChat and other apps).
 * Desktop, or a phone that cannot share that file type, downloads it.
 */
import { computeIsMobileClient } from '@/utils/isMobileClient'

export type DeliverExportResult = 'shared' | 'downloaded' | 'cancelled'

const MIME_BY_EXTENSION: Record<string, string> = {
  png: 'image/png',
  svg: 'image/svg+xml',
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  mg: 'application/octet-stream',
}

function mimeForFile(filename: string, blobType: string): string {
  if (blobType && blobType !== 'application/octet-stream') {
    return blobType
  }
  const extension = filename.split('.').pop()?.toLowerCase() ?? ''
  return MIME_BY_EXTENSION[extension] ?? (blobType || 'application/octet-stream')
}

function triggerDownloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.download = filename
  link.href = url
  link.click()
  URL.revokeObjectURL(url)
}

function canShareFile(file: File): boolean {
  if (typeof navigator.share !== 'function') {
    return false
  }
  if (typeof navigator.canShare !== 'function') {
    return true
  }
  try {
    return navigator.canShare({ files: [file] })
  } catch {
    return false
  }
}

export async function deliverExportFile(
  blob: Blob,
  filename: string
): Promise<DeliverExportResult> {
  if (computeIsMobileClient()) {
    const file = new File([blob], filename, { type: mimeForFile(filename, blob.type) })
    if (canShareFile(file)) {
      try {
        await navigator.share({ files: [file], title: filename })
        return 'shared'
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return 'cancelled'
        }
      }
    }
  }
  triggerDownloadBlob(blob, filename)
  return 'downloaded'
}

export async function deliverExportDataUrl(
  dataUrl: string,
  filename: string
): Promise<DeliverExportResult> {
  const response = await fetch(dataUrl)
  const blob = await response.blob()
  return deliverExportFile(blob, filename)
}
