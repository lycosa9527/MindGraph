import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  processShowcaseGalleryImagePick,
  type ShowcaseGalleryPickEvent,
} from '@/composables/showcase/processShowcaseGalleryImagePick'

vi.mock('@/composables/media/resizeImageFileForShowcaseGallery', async () => {
  const actual = await vi.importActual<
    typeof import('@/composables/media/resizeImageFileForShowcaseGallery')
  >('@/composables/media/resizeImageFileForShowcaseGallery')
  return {
    ...actual,
    resizeImageFileForShowcaseGallery: vi.fn(async (file: File) => {
      return new File([new Uint8Array(100)], file.name.replace(/\.jpeg$/i, '.jpg'), {
        type: file.type || 'image/jpeg',
        lastModified: Date.now(),
      })
    }),
  }
})

describe('processShowcaseGalleryImagePick', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('emits start/item/done for valid images and applies size checks after process', async () => {
    const events: ShowcaseGalleryPickEvent[] = []
    const drafts: File[] = []
    const files = [
      new File([new Uint8Array(10)], 'a.jpg', { type: 'image/jpeg' }),
      new File([new Uint8Array(10)], 'b.png', { type: 'image/png' }),
    ]

    await processShowcaseGalleryImagePick({
      files,
      signal: new AbortController().signal,
      maxPerFileBytes: 1024,
      maxTotalBytes: 10_000,
      isImageFile: (name) => /\.(jpe?g|png|webp|gif)$/i.test(name),
      galleryAtLimit: () => drafts.length >= 15,
      currentDraftBytes: () => drafts.reduce((sum, file) => sum + file.size, 0),
      onEvent: (event) => {
        events.push(event)
        if (event.type === 'item') {
          drafts.push(event.processed)
        }
      },
    })

    expect(events[0]).toEqual({ type: 'start', total: 2 })
    expect(events.filter((event) => event.type === 'item')).toHaveLength(2)
    expect(events.at(-1)).toEqual({ type: 'done', added: 2 })
    expect(drafts).toHaveLength(2)
  })

  it('rejects invalid types without adding drafts', async () => {
    const events: ShowcaseGalleryPickEvent[] = []
    const files = [new File([new Uint8Array(10)], 'notes.txt', { type: 'text/plain' })]

    await processShowcaseGalleryImagePick({
      files,
      signal: new AbortController().signal,
      maxPerFileBytes: 1024,
      maxTotalBytes: 10_000,
      isImageFile: (name) => /\.(jpe?g|png|webp|gif)$/i.test(name),
      galleryAtLimit: () => false,
      currentDraftBytes: () => 0,
      onEvent: (event) => {
        events.push(event)
      },
    })

    expect(events.some((event) => event.type === 'reject' && event.reason === 'invalid_type')).toBe(
      true
    )
    expect(events.some((event) => event.type === 'item')).toBe(false)
  })

  it('rejects when the gallery is already at the item limit', async () => {
    const events: ShowcaseGalleryPickEvent[] = []
    const files = [new File([new Uint8Array(10)], 'ok.jpg', { type: 'image/jpeg' })]

    await processShowcaseGalleryImagePick({
      files,
      signal: new AbortController().signal,
      maxPerFileBytes: 1024,
      maxTotalBytes: 10_000,
      isImageFile: () => true,
      galleryAtLimit: () => true,
      currentDraftBytes: () => 0,
      onEvent: (event) => {
        events.push(event)
      },
    })

    expect(events.some((event) => event.type === 'reject' && event.reason === 'gallery_limit')).toBe(
      true
    )
    expect(events.some((event) => event.type === 'item')).toBe(false)
  })

  it('emits aborted and stops when the signal is cancelled mid-batch', async () => {
    const { resizeImageFileForShowcaseGallery } = await import(
      '@/composables/media/resizeImageFileForShowcaseGallery'
    )
    const controller = new AbortController()
    let calls = 0
    vi.mocked(resizeImageFileForShowcaseGallery).mockImplementation(async (file: File) => {
      calls += 1
      if (calls === 1) {
        controller.abort()
      }
      return new File([new Uint8Array(50)], file.name, { type: 'image/jpeg' })
    })

    const events: ShowcaseGalleryPickEvent[] = []
    const files = [
      new File([new Uint8Array(10)], 'a.jpg', { type: 'image/jpeg' }),
      new File([new Uint8Array(10)], 'b.jpg', { type: 'image/jpeg' }),
    ]

    await processShowcaseGalleryImagePick({
      files,
      signal: controller.signal,
      maxPerFileBytes: 1024,
      maxTotalBytes: 10_000,
      isImageFile: () => true,
      galleryAtLimit: () => false,
      currentDraftBytes: () => 0,
      onEvent: (event) => {
        events.push(event)
      },
    })

    expect(events.some((event) => event.type === 'aborted')).toBe(true)
    expect(events.some((event) => event.type === 'done')).toBe(false)
    expect(calls).toBe(1)
  })
})
