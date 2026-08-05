/**
 * Thumbnail capture helpers for the Showcase publish modal.
 * Never mutates the editor diagram Pinia store — PNG export / existing thumbs only.
 */
import type { Ref } from 'vue'

import {
  acceptThumbnailBlob,
  dataUrlToPngBlob,
  imageFileToPngBlob,
  isDiagramImageFile,
} from '@/components/showcase/showcaseShared'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'
import {
  fetchDiagramSpecPngBlob,
} from '@/utils/showcaseDiagramThumbnail'

import type { GalleryImageDraft } from './usePublishShowcaseGalleryDrafts'

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
  const dataUrl = await htmlToImage.toPng(container, { pixelRatio: 1.5, cacheBust: true })
  return acceptThumbnailBlob(await dataUrlToPngBlob(dataUrl))
}

export async function resolveHistoryDiagramThumbnail(
  diagram: SavedDiagram | null,
): Promise<Blob | null> {
  if (!diagram) return null

  if (diagram.thumbnail) {
    const fromList = await acceptThumbnailBlob(await dataUrlToPngBlob(diagram.thumbnail))
    if (fromList) return fromList
  }

  const savedDiagramsStore = useSavedDiagramsStore()
  const cached = savedDiagramsStore.getCachedDiagram(diagram.id)
  if (cached?.thumbnail) {
    const fromCache = await acceptThumbnailBlob(await dataUrlToPngBlob(cached.thumbnail))
    if (fromCache) return fromCache
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
          const prepared = await acceptThumbnailBlob(await imgRes.blob())
          if (prepared) return prepared
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
): Promise<Blob | null> {
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
}): Promise<Blob | null> {
  if (options.fromCanvas) {
    return captureCanvasThumbnail(options.props)
  }
  const firstGalleryImage = options.galleryImageDrafts[0]
  if (firstGalleryImage) {
    const fromGallery = await imageFileToPngBlob(firstGalleryImage.file)
    if (fromGallery) return fromGallery
  }
  if (options.uploadedFile && isDiagramImageFile(options.uploadedFile.name)) {
    const fromUpload = await imageFileToPngBlob(options.uploadedFile)
    if (fromUpload) return fromUpload
  }

  if (options.showPublishDiagramPreview && options.inlinePreviewRef.value) {
    const fromInline = await options.inlinePreviewRef.value.captureThumbnail?.()
    const prepared = await acceptThumbnailBlob(fromInline ?? null)
    if (prepared) return prepared
  }

  if (options.uploadedMgSpec) {
    const fromSpec = await resolveSpecThumbnail(
      options.uploadedMgSpec,
      options.publishPreviewDiagramType,
    )
    if (fromSpec) return fromSpec
  }

  if (options.selectedDiagramSpec) {
    const fromSpec = await resolveSpecThumbnail(
      options.selectedDiagramSpec,
      options.publishPreviewDiagramType,
    )
    if (fromSpec) return fromSpec
  }

  if (options.selectedDiagram) {
    const fromHistory = await resolveHistoryDiagramThumbnail(options.selectedDiagram)
    if (fromHistory) return fromHistory
  }

  return null
}
