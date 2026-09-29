/**
 * Renders missing demo-list thumbnails one row at a time and uploads them.
 * Close and autosave do not call this.
 */
import { ref } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import type { LibraryDemoThumbnail } from '@/composables/demo/libraryDemoApi'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { apiUpload } from '@/utils/apiClient'
import { fetchDiagramSpecPngBlob } from '@/utils/showcaseDiagramThumbnail'

export function demoThumbnailIsStale(
  stored: LibraryDemoThumbnail | undefined,
  diagramUpdatedAt: string
): boolean {
  if (!stored?.updatedAt) return true
  const diagramMs = Date.parse(diagramUpdatedAt)
  const storedMs = Date.parse(stored.updatedAt)
  if (Number.isNaN(diagramMs)) return false
  if (Number.isNaN(storedMs)) return true
  return diagramMs > storedMs
}

/** True only when this save must render a new image. */
export function demoThumbnailNeedsRender(
  stored: LibraryDemoThumbnail | undefined,
  diagramUpdatedAt: string,
  diagramThumbnail: string | null
): boolean {
  if (!demoThumbnailIsStale(stored, diagramUpdatedAt)) return false
  if (!stored && diagramThumbnail) return false
  return true
}

export function useDemoListThumbnails() {
  const savedDiagrams = useSavedDiagramsStore()
  const notifications = useNotifications()
  const thumbnails = ref<Record<string, LibraryDemoThumbnail>>({})
  const renderingId = ref<string | null>(null)
  let job = 0

  function cancel(): void {
    job += 1
    renderingId.value = null
  }

  function listThumb(diagramId: string, fallback: string | null): string | null {
    return thumbnails.value[diagramId]?.url || fallback || null
  }

  async function specFor(diagramId: string): Promise<Record<string, unknown> | null> {
    const cached = savedDiagrams.getCachedDiagramSpec(diagramId)
    if (cached) return cached
    const result = await savedDiagrams.getDiagram(diagramId)
    if (!result.ok) return null
    return result.diagram.spec
  }

  async function uploadOne(diagram: SavedDiagram, token: number): Promise<boolean> {
    const spec = await specFor(diagram.id)
    if (token !== job || !spec) return false
    const blob = await fetchDiagramSpecPngBlob(spec, diagram.diagram_type)
    if (token !== job || !blob) return false
    const form = new FormData()
    form.append('diagram_id', diagram.id)
    form.append('file', blob, 'thumbnail.png')
    try {
      const response = await apiUpload('/api/auth/library-demo/thumbnails', form)
      if (token !== job || !response.ok) return false
      const payload = (await response.json()) as { url?: unknown }
      if (token !== job || typeof payload.url !== 'string' || !payload.url) return false
      thumbnails.value = {
        ...thumbnails.value,
        [diagram.id]: { url: payload.url, updatedAt: diagram.updated_at },
      }
      return true
    } catch {
      // A failed render keeps the thumbnail this list already had.
      return false
    }
  }

  async function publish(diagrams: SavedDiagram[], onStored: () => void): Promise<boolean> {
    const token = job + 1
    job = token
    let failed = false
    let attempted = 0
    let stamped = false
    for (const diagram of diagrams) {
      if (token !== job) return false
      const stored = thumbnails.value[diagram.id]
      if (!demoThumbnailNeedsRender(stored, diagram.updated_at, diagram.thumbnail)) {
        if (!stored && diagram.thumbnail) {
          thumbnails.value = {
            ...thumbnails.value,
            [diagram.id]: { url: '', updatedAt: diagram.updated_at },
          }
          stamped = true
        }
        continue
      }
      attempted += 1
      renderingId.value = diagram.id
      const ok = await uploadOne(diagram, token)
      if (token !== job) return false
      if (!ok) failed = true
    }
    if (token !== job) return false
    renderingId.value = null
    if (stamped || attempted > 0) onStored()
    if (attempted === 0) return true
    if (failed) {
      notifications.warningKey('sidebar.demo.thumbsPartial')
      return true
    }
    notifications.successKey('sidebar.demo.thumbsReady')
    return true
  }

  return { thumbnails, renderingId, listThumb, publish, cancel }
}
