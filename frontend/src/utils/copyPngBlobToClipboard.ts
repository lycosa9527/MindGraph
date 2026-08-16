/**
 * Async Clipboard API — same pattern as Excalidraw `copyBlobToClipboardAsPng`.
 * https://github.com/excalidraw/excalidraw/blob/master/packages/excalidraw/clipboard.ts
 *
 * `navigator.clipboard.write` + `ClipboardItem({ 'image/png': blob | Promise<Blob> })`.
 * Pass a Promise so Safari can keep the user-gesture; if a browser rejects Promise
 * items (Firefox MIME quirk), retry with the resolved Blob.
 */

function isPromiseLike(value: Blob | Promise<Blob>): value is Promise<Blob> {
  return typeof (value as Promise<Blob>).then === 'function'
}

export function canWriteImageToClipboard(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    typeof ClipboardItem !== 'undefined' &&
    Boolean(navigator.clipboard?.write)
  )
}

export async function copyPngBlobToClipboard(blob: Blob | Promise<Blob>): Promise<void> {
  if (!canWriteImageToClipboard()) {
    throw new Error('Clipboard image write is not supported')
  }
  try {
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
  } catch (error) {
    if (!isPromiseLike(blob)) {
      throw error
    }
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': await blob })])
  }
}

export async function copyPngBlobWithFallback(
  source: Promise<Blob>,
  download: (blob: Blob) => void
): Promise<'copied' | 'downloaded'> {
  if (canWriteImageToClipboard()) {
    try {
      await copyPngBlobToClipboard(source)
      return 'copied'
    } catch (writeError) {
      let resolved: Blob
      try {
        resolved = await source
      } catch {
        throw writeError
      }
      if (resolved.size === 0) {
        throw writeError
      }
      download(resolved)
      return 'downloaded'
    }
  }
  const blob = await source
  if (blob.size === 0) {
    throw new Error('Clipboard export produced empty image')
  }
  download(blob)
  return 'downloaded'
}
