/**
 * Gallery draft state for the Case Square publish modal.
 */
import { computed, ref } from 'vue'

import {
  DIAGRAM_GALLERY_MAX_ITEMS,
} from '@/components/caseSquare/caseSquareGallery'
import { cloneCaseSquareDiagramSpec } from '@/utils/caseSquareDiagramThumbnail'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'

export type GalleryImageDraft = { id: string; file: File; filename: string; previewUrl: string }
export type GalleryDiagramDraft = {
  id: string
  diagram: SavedDiagram
  spec: Record<string, unknown> | null
  title: string
}
export type GalleryExistingImage = { path: string; filename: string; url: string }

export function newGalleryId(): string {
  return `g-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function usePublishCaseSquareGalleryDrafts() {
  const savedDiagramsStore = useSavedDiagramsStore()

  const galleryImageDrafts = ref<GalleryImageDraft[]>([])
  const galleryDiagramDrafts = ref<GalleryDiagramDraft[]>([])
  const galleryExistingImages = ref<GalleryExistingImage[]>([])

  const galleryTotalCount = computed(
    () =>
      galleryImageDrafts.value.length +
      galleryDiagramDrafts.value.length +
      galleryExistingImages.value.length
  )

  const galleryAtLimit = computed(() => galleryTotalCount.value >= DIAGRAM_GALLERY_MAX_ITEMS)

  function clearGalleryDrafts(): void {
    for (const draft of galleryImageDrafts.value) {
      URL.revokeObjectURL(draft.previewUrl)
    }
    galleryImageDrafts.value = []
    galleryDiagramDrafts.value = []
    galleryExistingImages.value = []
  }

  function removeGalleryImageDraft(id: string): void {
    const index = galleryImageDrafts.value.findIndex((entry) => entry.id === id)
    if (index < 0) return
    URL.revokeObjectURL(galleryImageDrafts.value[index].previewUrl)
    galleryImageDrafts.value.splice(index, 1)
  }

  function removeGalleryExistingImage(index: number): void {
    galleryExistingImages.value.splice(index, 1)
  }

  function removeGalleryDiagramDraft(id: string): void {
    galleryDiagramDrafts.value = galleryDiagramDrafts.value.filter((entry) => entry.id !== id)
  }

  async function loadGalleryDiagramSpec(draft: GalleryDiagramDraft): Promise<boolean> {
    if (draft.spec) return true
    try {
      const cached = savedDiagramsStore.getCachedDiagramSpec(draft.diagram.id)
      if (cached) {
        draft.spec = cloneCaseSquareDiagramSpec(cached)
        return true
      }
      const result = await savedDiagramsStore.getDiagram(draft.diagram.id)
      if (result.ok) {
        draft.spec = cloneCaseSquareDiagramSpec(result.diagram.spec)
        return true
      }
    } catch {
      return false
    }
    return false
  }

  function pushGalleryImageDraft(file: File): void {
    galleryImageDrafts.value.push({
      id: newGalleryId(),
      file,
      filename: file.name,
      previewUrl: URL.createObjectURL(file),
    })
  }

  async function addGalleryDiagramDraft(
    diagram: SavedDiagram,
    diagramTypeValue: string,
    setDiagramType: (value: string) => void,
    diagramTypeFromSaved: (raw: string) => string,
  ): Promise<GalleryDiagramDraft | null> {
    if (galleryDiagramDrafts.value.some((entry) => entry.diagram.id === diagram.id)) {
      return null
    }
    if (galleryAtLimit.value) {
      return null
    }
    const draft: GalleryDiagramDraft = {
      id: newGalleryId(),
      diagram,
      spec: null,
      title: diagram.title,
    }
    const cachedSpec = savedDiagramsStore.getCachedDiagramSpec(diagram.id)
    if (cachedSpec) {
      draft.spec = cloneCaseSquareDiagramSpec(cachedSpec)
    }
    galleryDiagramDrafts.value.push(draft)
    if (!diagramTypeValue) {
      setDiagramType(diagramTypeFromSaved(diagram.diagram_type) || 'mind_map')
    }
    if (!draft.spec) {
      await loadGalleryDiagramSpec(draft)
    }
    return draft
  }

  return {
    galleryImageDrafts,
    galleryDiagramDrafts,
    galleryExistingImages,
    galleryTotalCount,
    galleryAtLimit,
    clearGalleryDrafts,
    newGalleryId,
    removeGalleryImageDraft,
    removeGalleryExistingImage,
    removeGalleryDiagramDraft,
    loadGalleryDiagramSpec,
    pushGalleryImageDraft,
    addGalleryDiagramDraft,
  }
}
