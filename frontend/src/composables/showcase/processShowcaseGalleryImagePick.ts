/**
 * Event-driven async pipeline for showcase gallery image picks.
 * Sequential resize (memory-safe), abortable, yields to the event loop between files.
 */

import {
  isShowcaseGalleryAbortError,
  resizeImageFileForShowcaseGallery,
} from '@/composables/media/resizeImageFileForShowcaseGallery'

export type ShowcaseGalleryPickRejectReason =
  | 'invalid_type'
  | 'too_large'
  | 'total_too_large'
  | 'gallery_limit'

export type ShowcaseGalleryPickEvent =
  | { type: 'start'; total: number }
  | {
      type: 'item'
      source: File
      processed: File
      index: number
      total: number
    }
  | {
      type: 'reject'
      source: File
      reason: ShowcaseGalleryPickRejectReason
      index: number
      total: number
    }
  | { type: 'done'; added: number }
  | { type: 'aborted'; added: number }

export type ProcessShowcaseGalleryImagePickOptions = {
  files: readonly File[]
  signal: AbortSignal
  maxPerFileBytes: number
  maxTotalBytes: number
  isImageFile: (name: string) => boolean
  galleryAtLimit: () => boolean
  currentDraftBytes: () => number
  onEvent: (event: ShowcaseGalleryPickEvent) => void | Promise<void>
}

function abortError(): DOMException {
  return new DOMException('Aborted', 'AbortError')
}

function throwIfAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    throw abortError()
  }
}

/** Yield so the UI can paint / handle input between heavy decode/encode work. */
export function yieldToEventLoop(signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    let settled = false
    const timer = window.setTimeout(() => {
      if (settled) return
      settled = true
      signal?.removeEventListener('abort', onAbort)
      if (signal?.aborted) {
        reject(abortError())
        return
      }
      resolve()
    }, 0)
    const onAbort = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

/**
 * Process picked gallery images one-by-one and emit lifecycle events.
 * Size caps apply to the processed payload (after downscale / EXIF strip).
 */
export async function processShowcaseGalleryImagePick(
  options: ProcessShowcaseGalleryImagePickOptions
): Promise<void> {
  const {
    files,
    signal,
    maxPerFileBytes,
    maxTotalBytes,
    isImageFile,
    galleryAtLimit,
    currentDraftBytes,
    onEvent,
  } = options

  const total = files.length
  let added = 0

  const emit = async (event: ShowcaseGalleryPickEvent): Promise<void> => {
    await onEvent(event)
  }

  try {
    throwIfAborted(signal)
    await emit({ type: 'start', total })

    for (let index = 0; index < files.length; index += 1) {
      throwIfAborted(signal)
      const source = files[index]

      if (galleryAtLimit()) {
        await emit({
          type: 'reject',
          source,
          reason: 'gallery_limit',
          index,
          total,
        })
        break
      }

      if (!isImageFile(source.name)) {
        await emit({
          type: 'reject',
          source,
          reason: 'invalid_type',
          index,
          total,
        })
        continue
      }

      const processed = await resizeImageFileForShowcaseGallery(source, { signal })
      throwIfAborted(signal)

      if (processed.size > maxPerFileBytes) {
        await emit({
          type: 'reject',
          source,
          reason: 'too_large',
          index,
          total,
        })
        continue
      }

      if (currentDraftBytes() + processed.size > maxTotalBytes) {
        await emit({
          type: 'reject',
          source,
          reason: 'total_too_large',
          index,
          total,
        })
        break
      }

      await emit({
        type: 'item',
        source,
        processed,
        index,
        total,
      })
      added += 1

      if (index < files.length - 1) {
        await yieldToEventLoop(signal)
      }
    }

    throwIfAborted(signal)
    await emit({ type: 'done', added })
  } catch (error) {
    if (isShowcaseGalleryAbortError(error) || signal.aborted) {
      await emit({ type: 'aborted', added })
      return
    }
    throw error
  }
}
