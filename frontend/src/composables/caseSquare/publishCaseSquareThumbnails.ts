/**
 * Thumbnail capture helpers for the Case Square publish modal.
 */
import { nextTick, type Ref } from 'vue'

import {
  dataUrlToPngBlob,
  imageFileToPngBlob,
  isDiagramImageFile,
  isValidThumbnailBlob,
} from '@/components/caseSquare/caseSquareShared'
import { eventBus } from '@/composables/core/useEventBus'
import { setPresentationDiagramEditLocked } from '@/composables/presentation/presentationDiagramEdit'
import { useDiagramStore } from '@/stores'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import {
  cloneCaseSquareDiagramSpec,
  fetchDiagramSpecPngBlob,
  resolveCaseSquareDiagramType,
} from '@/utils/caseSquareDiagramThumbnail'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

import type { GalleryImageDraft } from './usePublishCaseSquareGalleryDrafts'

type ThumbnailProps = {
  getContainer?: () => HTMLElement | null
  prepareForThumbnail?: () => Promise<void>
}

type InlinePreview = {
  captureThumbnail?: () => Promise<Blob | null>
}

export async function captureCanvasThumbnail(props: ThumbnailProps): Promise<Blob | null> {
  const container = props.getContainer?.()
  if (!container) return null
  await props.prepareForThumbnail?.()
  const htmlToImage = await import('html-to-image')
  const dataUrl = await htmlToImage.toPng(container, { pixelRatio: 2, cacheBust: true })
  return dataUrlToPngBlob(dataUrl)
}

export async function captureSpecThumbnailClient(
  spec: Record<string, unknown>,
  diagramTypeValue: string,
  thumbnailCaptureHost: Ref<HTMLElement | null>,
  showThumbnailCapture: Ref<boolean>,
): Promise<Blob | null> {
  const diagramStore = useDiagramStore()
  const specClone = cloneCaseSquareDiagramSpec(spec)
  const normalizedType = resolveCaseSquareDiagramType(specClone, diagramTypeValue)
  const backup = {
    type: diagramStore.type,
    spec: diagramStore.getSpecForSave() as Record<string, unknown> | null,
  }

  if (!diagramStore.loadFromSpec(specClone, normalizedType, { emitLoaded: false })) {
    return null
  }

  showThumbnailCapture.value = true
  setPresentationDiagramEditLocked(true)
  try {
    await nextTick()
    await waitForNextPaint()
    eventBus.emit('view:fit_to_canvas_requested', { animate: false, forExport: true })
    try {
      await new Promise<void>((resolve, reject) => {
        let off: (() => void) | null = null
        const timer = window.setTimeout(() => {
          off?.()
          reject(new Error('fit timeout'))
        }, 12_000)
        off = eventBus.once('view:fit_completed', () => {
          window.clearTimeout(timer)
          resolve()
        })
      })
    } catch {
      // Best-effort fit before capture.
    }
    await waitForNextPaint()
    await new Promise((resolve) => setTimeout(resolve, 600))
    const container = thumbnailCaptureHost.value
    if (!container) return null
    const captureTarget =
      (container.querySelector('.diagram-canvas') as HTMLElement | null) ?? container
    const htmlToImage = await import('html-to-image')
    const dataUrl = await htmlToImage.toPng(captureTarget, { pixelRatio: 2, cacheBust: true })
    const blob = await dataUrlToPngBlob(dataUrl)
    return isValidThumbnailBlob(blob) ? blob : null
  } catch {
    return null
  } finally {
    showThumbnailCapture.value = false
    setPresentationDiagramEditLocked(false)
    if (backup.type && backup.spec) {
      diagramStore.loadFromSpec(backup.spec, backup.type as DiagramType, { emitLoaded: false })
    }
  }
}

export async function resolveHistoryDiagramThumbnail(
  diagram: SavedDiagram | null,
): Promise<Blob | null> {
  if (!diagram) return null

  if (diagram.thumbnail) {
    const fromList = await dataUrlToPngBlob(diagram.thumbnail)
    if (isValidThumbnailBlob(fromList)) return fromList
  }

  const savedDiagramsStore = useSavedDiagramsStore()
  const cached = savedDiagramsStore.getCachedDiagram(diagram.id)
  if (cached?.thumbnail) {
    const fromCache = await dataUrlToPngBlob(cached.thumbnail)
    if (isValidThumbnailBlob(fromCache)) return fromCache
  }

  try {
    const res = await fetch(`/api/diagrams/${diagram.id}/png`, {
      credentials: 'include',
    })
    if (res.ok) {
      const data = (await res.json()) as { url?: string }
      if (data.url) {
        const imgRes = await fetch(data.url, { credentials: 'include', cache: 'no-store' })
        if (imgRes.ok) {
          const blob = await imgRes.blob()
          if (isValidThumbnailBlob(blob)) return blob
        }
      }
    }
  } catch {
    // fall through
  }

  return null
}

export async function resolveSpecThumbnail(
  spec: Record<string, unknown>,
  diagramTypeValue: string,
  thumbnailCaptureHost: Ref<HTMLElement | null>,
  showThumbnailCapture: Ref<boolean>,
): Promise<Blob | null> {
  const fromClient = await captureSpecThumbnailClient(
    spec,
    diagramTypeValue,
    thumbnailCaptureHost,
    showThumbnailCapture,
  )
  if (fromClient) return fromClient
  return fetchDiagramSpecPngBlob(spec, diagramTypeValue)
}

export async function resolvePublishThumbnail(options: {
  fromCanvas: boolean
  props: ThumbnailProps
  galleryImageDrafts: GalleryImageDraft[]
  uploadedFile: File | null
  showPublishDiagramPreview: boolean
  inlinePreviewRef: Ref<InlinePreview | null>
  uploadedMgSpec: Record<string, unknown> | null
  selectedDiagramSpec: Record<string, unknown> | null
  selectedDiagram: SavedDiagram | null
  publishPreviewDiagramType: string
  thumbnailCaptureHost: Ref<HTMLElement | null>
  showThumbnailCapture: Ref<boolean>
}): Promise<Blob | null> {
  if (options.fromCanvas) {
    return captureCanvasThumbnail(options.props)
  }
  const firstGalleryImage = options.galleryImageDrafts[0]
  if (firstGalleryImage) {
    return imageFileToPngBlob(firstGalleryImage.file)
  }
  if (options.uploadedFile && isDiagramImageFile(options.uploadedFile.name)) {
    return imageFileToPngBlob(options.uploadedFile)
  }

  if (options.showPublishDiagramPreview && options.inlinePreviewRef.value) {
    const fromInline = await options.inlinePreviewRef.value.captureThumbnail?.()
    if (isValidThumbnailBlob(fromInline ?? null)) return fromInline ?? null
  }

  if (options.uploadedMgSpec) {
    const fromSpec = await resolveSpecThumbnail(
      options.uploadedMgSpec,
      options.publishPreviewDiagramType,
      options.thumbnailCaptureHost,
      options.showThumbnailCapture,
    )
    if (fromSpec) return fromSpec
  }

  if (options.selectedDiagramSpec) {
    const fromSpec = await resolveSpecThumbnail(
      options.selectedDiagramSpec,
      options.publishPreviewDiagramType,
      options.thumbnailCaptureHost,
      options.showThumbnailCapture,
    )
    if (fromSpec) return fromSpec
  }

  if (options.selectedDiagram) {
    const fromHistory = await resolveHistoryDiagramThumbnail(options.selectedDiagram)
    if (fromHistory) return fromHistory
  }

  return null
}
