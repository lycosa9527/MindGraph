/**
 * Saved Diagrams Store - Pinia store for user's saved diagram history
 * Fetches from /api/diagrams endpoint
 *
 * Enhanced with auto-save functionality:
 * - Tracks active diagram on canvas (if already saved to library)
 * - Auto-saves diagrams in background when slots available
 * - Supports manual save with slot management modal
 *
 * Security:
 * - Validates spec size before sending to backend (max 500KB)
 * - Validates thumbnail size (max ~100KB base64)
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { notify } from '@/composables/core/notifications'
import { applyThinkingCoinMutation, extractThinkingCoinsFooter } from '@/composables/auth/useThinkingCoinSync'
import { getDefaultDiagramName } from '@/composables'
import { SAVE } from '@/config'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'
import { i18n } from '@/i18n'
import type { DiagramId, DiagramType } from '@/types'
import { authFetch } from '@/utils/api'
import { hasDiagramSaveLimit } from '@/utils/diagramLimit'

import { syncFolderDiagramCounts } from '@/composables/sidebar/useDiagramArchiveHistory'
import { useAuthStore } from './auth'
import { useDiagramStore } from './diagram'
import { useLLMResultsStore } from './llmResults'
import { usePanelsStore } from './panels'
import { getDefaultTemplate, loadSpecForDiagramType } from './specLoader'

export type GetDiagramFailureReason =
  | 'not_found'
  | 'forbidden'
  | 'network'
  | 'unauthenticated'

export type GetDiagramResult =
  | { ok: true; diagram: SavedDiagramFull }
  | { ok: false; reason: GetDiagramFailureReason; status: number | null }
import { useUIStore } from './ui'

// Security constants - must match backend limits
const MAX_THUMBNAIL_SIZE = 150000 // Max base64 chars (~100KB decoded)

function diagramLimitMessage(max: number, apiDetail?: string): string {
  if (apiDetail && apiDetail.trim()) {
    return apiDetail.trim()
  }
  if (hasDiagramSaveLimit(max)) {
    return i18n.global.t('auth.diagramLimitReached', { max }) as string
  }
  return i18n.global.t('library.slotFull.title') as string
}

function notifyDiagramLimitReached(max: number, apiDetail?: string): void {
  notify.warning(diagramLimitMessage(max, apiDetail))
}

async function readDiagramApiErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    const detail = payload.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim()
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string }
      if (typeof first?.msg === 'string' && first.msg.trim()) {
        return first.msg.trim()
      }
    }
  } catch {
    // ignore parse errors
  }
  return ''
}

/**
 * Check if a diagram spec is empty/unmodified (still matches default template)
 *
 * This function compares the current diagram against the default template by:
 * 1. Loading the default template for the diagram type
 * 2. Converting it to nodes using the same loader function
 * 3. Comparing node texts (normalized and sorted) to detect if diagram is unchanged
 *
 * This approach is more accurate than regex patterns because:
 * - Uses actual template data (single source of truth)
 * - Automatically adapts if templates change
 * - Avoids false positives from regex matching
 * - Compares structure, not just text patterns
 */
function isDiagramEmpty(spec: Record<string, unknown>, diagramType: DiagramType): boolean {
  // Check if spec has nodes array (saved diagram format)
  if (!('nodes' in spec) || !Array.isArray(spec.nodes)) {
    return false
  }

  const currentNodes = spec.nodes as Array<Record<string, unknown>>

  // If no nodes, consider it empty
  if (currentNodes.length === 0) {
    return true
  }

  const zhTemplate = getDefaultTemplate(diagramType, 'zh')
  const enTemplate = getDefaultTemplate(diagramType, 'en')
  const templates = [zhTemplate, enTemplate].filter((t): t is Record<string, unknown> => t != null)
  if (templates.length === 0) {
    return false
  }

  const normalizeTexts = (nodes: Array<{ text: string }>): string[] => {
    return nodes
      .map((node) => node.text)
      .filter((text) => text.length > 0)
      .sort()
  }

  const currentTexts = normalizeTexts(
    currentNodes.map((node) => ({
      text: String(node.text || '').trim(),
    }))
  )

  for (const defaultTemplate of templates) {
    let defaultNodes: Array<{ text: string }>
    try {
      const defaultResult = loadSpecForDiagramType(defaultTemplate, diagramType)
      defaultNodes = defaultResult.nodes.map((node) => ({
        text: String(node.text || '').trim(),
      }))
    } catch (error) {
      console.warn('[SavedDiagrams] Failed to load default template for comparison:', error)
      continue
    }
    const defaultTexts = normalizeTexts(defaultNodes)
    if (currentTexts.length !== defaultTexts.length) {
      continue
    }
    if (currentTexts.every((text, index) => text === defaultTexts[index])) {
      return true
    }
  }
  return false
}

// Types
export interface SavedDiagram {
  id: DiagramId
  title: string
  diagram_type: string
  thumbnail: string | null
  updated_at: string // ISO date string
  is_pinned: boolean
  workshop_active?: boolean
  folder_id?: string | null
}

export interface DiagramFolder {
  id: string
  name: string
  sort_order: number
  diagram_count: number
  created_at: string
  updated_at: string
}

export interface DiagramFolderListResponse {
  folders: DiagramFolder[]
}

export interface SavedDiagramFull extends SavedDiagram {
  spec: Record<string, unknown>
  language: string
  created_at: string
}

export interface DiagramListResponse {
  diagrams: SavedDiagram[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  max_diagrams: number
}

// Auto-save result types
export interface AutoSaveResult {
  success: boolean
  action: 'saved' | 'updated' | 'skipped' | 'error'
  diagramId?: string
  error?: string
}

export const useSavedDiagramsStore = defineStore('savedDiagrams', () => {
  // State
  const diagrams = ref<SavedDiagram[]>([])
  const folders = ref<DiagramFolder[]>([])
  const foldersLoadFailed = ref(false)
  const total = ref(0)
  const maxDiagrams = ref(0)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentDiagramId = ref<string | null>(null)

  // Active diagram tracking - tracks if current canvas diagram is saved to library
  const activeDiagramId = ref<string | null>(null)
  const isAutoSaving = ref(false)

  /** In-memory cache so showcase / history picker can show previews instantly. */
  const diagramDetailCache = new Map<string, SavedDiagramFull>()

  // Getters
  const authStore = useAuthStore()
  const uiStore = useUIStore()
  const hasSaveLimit = computed(() => hasDiagramSaveLimit(maxDiagrams.value))
  const savedDiagramCount = computed(() => total.value)
  const canSaveMore = computed(
    () => !hasSaveLimit.value || savedDiagramCount.value < maxDiagrams.value
  )
  const remainingSlots = computed(() =>
    hasSaveLimit.value ? maxDiagrams.value - savedDiagramCount.value : Number.POSITIVE_INFINITY
  )
  const isActiveDiagramSaved = computed(() => activeDiagramId.value !== null)
  const isSlotsFullyUsed = computed(
    () => hasSaveLimit.value && savedDiagramCount.value >= maxDiagrams.value
  )

  // Actions
  function applyFolderCounts(): void {
    folders.value = syncFolderDiagramCounts(folders.value, diagrams.value)
  }

  async function fetchDiagrams(page: number = 1, pageSize: number = 50): Promise<boolean> {
    if (!authStore.isAuthenticated) {
      diagrams.value = []
      folders.value = []
      foldersLoadFailed.value = false
      return false
    }

    isLoading.value = true
    error.value = null
    foldersLoadFailed.value = false

    try {
      const [diagramResponse, folderResponse] = await Promise.all([
        authFetch(`/api/diagrams?page=${page}&page_size=${pageSize}`),
        authFetch('/api/diagram-folders'),
      ])

      if (!diagramResponse.ok) {
        if (diagramResponse.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后查看图表')
          return false
        }
        throw new Error(`Failed to fetch diagrams: ${diagramResponse.status}`)
      }

      const data: DiagramListResponse = await diagramResponse.json()
      let merged = [...data.diagrams]
      let nextPage = data.page
      let hasMore = data.has_more
      while (hasMore && merged.length < data.total) {
        nextPage += 1
        const nextResponse = await authFetch(
          `/api/diagrams?page=${nextPage}&page_size=${pageSize}`
        )
        if (!nextResponse.ok) break
        const nextData: DiagramListResponse = await nextResponse.json()
        merged = [...merged, ...nextData.diagrams]
        hasMore = nextData.has_more
      }

      diagrams.value = merged
      total.value = data.total
      maxDiagrams.value = data.max_diagrams

      if (folderResponse.ok) {
        const folderData: DiagramFolderListResponse = await folderResponse.json()
        folders.value = folderData.folders
      } else {
        foldersLoadFailed.value = true
      }
      applyFolderCounts()

      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load diagrams'
      console.error('[SavedDiagrams] Fetch error:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function createFolder(name: string): Promise<DiagramFolder | null> {
    if (!authStore.isAuthenticated) return null
    try {
      const response = await authFetch('/api/diagram-folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      })
      if (!response.ok) {
        return null
      }
      const created = (await response.json()) as {
        id: string
        name: string
        sort_order: number
        created_at: string
        updated_at: string
      }
      const folder: DiagramFolder = {
        id: created.id,
        name: created.name,
        sort_order: created.sort_order,
        diagram_count: 0,
        created_at: created.created_at,
        updated_at: created.updated_at,
      }
      folders.value = [...folders.value, folder].sort(
        (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)
      )
      return folder
    } catch (e) {
      console.error('[SavedDiagrams] Create folder error:', e)
      return null
    }
  }

  async function renameFolder(folderId: string, name: string): Promise<boolean> {
    if (!authStore.isAuthenticated) return false
    try {
      const response = await authFetch(`/api/diagram-folders/${folderId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      })
      if (!response.ok) return false
      const entry = folders.value.find((f) => f.id === folderId)
      if (entry) {
        entry.name = name.trim()
      }
      return true
    } catch (e) {
      console.error('[SavedDiagrams] Rename folder error:', e)
      return false
    }
  }

  async function deleteFolder(folderId: string): Promise<boolean> {
    if (!authStore.isAuthenticated) return false
    try {
      const response = await authFetch(`/api/diagram-folders/${folderId}`, {
        method: 'DELETE',
      })
      if (response.status === 401) {
        authStore.handleTokenExpired('您的登录已过期，请重新登录')
        return false
      }
      if (!response.ok) {
        const detail = await readDiagramApiErrorDetail(response)
        error.value = detail || 'Failed to delete folder'
        console.error('[SavedDiagrams] Delete folder error:', response.status, detail)
        return false
      }
      folders.value = folders.value.filter((f) => f.id !== folderId)
      diagrams.value.forEach((d) => {
        if (d.folder_id === folderId) {
          d.folder_id = null
        }
      })
      applyFolderCounts()
      return true
    } catch (e) {
      console.error('[SavedDiagrams] Delete folder error:', e)
      return false
    }
  }

  async function moveDiagramToFolder(
    diagramId: string,
    folderId: string | null
  ): Promise<boolean> {
    if (!authStore.isAuthenticated) return false
    const entry = diagrams.value.find((d) => d.id === diagramId)
    const previousFolderId = entry?.folder_id ?? null
    if (entry) {
      entry.folder_id = folderId
      applyFolderCounts()
    }
    try {
      const response = await authFetch(`/api/diagrams/${diagramId}/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_id: folderId }),
      })
      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录')
          if (entry) {
            entry.folder_id = previousFolderId
            applyFolderCounts()
          }
          return false
        }
        const detail = await readDiagramApiErrorDetail(response)
        error.value = detail || 'Failed to move diagram'
        console.error('[SavedDiagrams] Move to folder error:', response.status, detail)
        if (entry) {
          entry.folder_id = previousFolderId
          applyFolderCounts()
        }
        return false
      }
      return true
    } catch (e) {
      if (entry) {
        entry.folder_id = previousFolderId
        applyFolderCounts()
      }
      console.error('[SavedDiagrams] Move to folder error:', e)
      return false
    }
  }

  /**
   * End the online workshop for a saved diagram (host only). Updates local
   * `workshop_active` when the server accepts the stop.
   */
  async function stopDiagramOnlineCollab(diagramId: string): Promise<boolean> {
    if (!authStore.isAuthenticated) {
      return false
    }
    try {
      const response = await authFetch(`/api/diagrams/${diagramId}/workshop/stop`, {
        method: 'POST',
      })
      if (!response.ok) {
        return false
      }
      const entry = diagrams.value.find((d) => d.id === diagramId)
      if (entry) {
        entry.workshop_active = false
      }
      return true
    } catch (e) {
      console.error('[SavedDiagrams] Stop workshop error:', e)
      return false
    }
  }

  function removeDiagramFromLocalList(diagramId: string): void {
    diagrams.value = diagrams.value.filter((d) => d.id !== diagramId)
    diagramDetailCache.delete(diagramId)
    if (total.value > 0) {
      total.value--
    }
    if (currentDiagramId.value === diagramId) {
      currentDiagramId.value = null
    }
    if (activeDiagramId.value === diagramId) {
      activeDiagramId.value = null
    }
  }

  function getCachedDiagram(diagramId: string): SavedDiagramFull | null {
    return diagramDetailCache.get(diagramId) ?? null
  }

  function getCachedDiagramSpec(diagramId: string): Record<string, unknown> | null {
    return diagramDetailCache.get(diagramId)?.spec ?? null
  }

  /**
   * Warm spec cache for history picker / publish preview (best-effort, non-blocking).
   */
  async function prefetchDiagramSpecs(diagramIds: string[], limit = 12): Promise<void> {
    if (!authStore.isAuthenticated) return
    const pending = diagramIds.filter((id) => !diagramDetailCache.has(id)).slice(0, limit)
    await Promise.all(
      pending.map(async (diagramId) => {
        const result = await getDiagram(diagramId)
        if (!result.ok) return
      })
    )
  }

  async function getDiagram(diagramId: string): Promise<GetDiagramResult> {
    if (!authStore.isAuthenticated) {
      return { ok: false, reason: 'unauthenticated', status: null }
    }

    const cached = diagramDetailCache.get(diagramId)
    if (cached) {
      return { ok: true, diagram: cached }
    }

    try {
      const response = await authFetch(`/api/diagrams/${diagramId}`)

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired(
            i18n.global.t('auth.sessionExpired') as string
          )
          return { ok: false, reason: 'unauthenticated', status: 401 }
        }
        if (response.status === 404) {
          console.warn(
            `[SavedDiagrams] Diagram ${diagramId} not found (404), removing from local list`
          )
          removeDiagramFromLocalList(diagramId)
          return { ok: false, reason: 'not_found', status: 404 }
        }
        if (response.status === 403) {
          return { ok: false, reason: 'forbidden', status: 403 }
        }
        return { ok: false, reason: 'network', status: response.status }
      }

      const diagram: SavedDiagramFull = await response.json()
      diagramDetailCache.set(diagramId, diagram)
      return { ok: true, diagram }
    } catch (e) {
      console.error('[SavedDiagrams] Get diagram error:', e)
      return { ok: false, reason: 'network', status: null }
    }
  }

  async function saveDiagram(
    title: string,
    diagramType: string,
    spec: Record<string, unknown>,
    language: string = 'zh',
    thumbnail: string | null = null
  ): Promise<SavedDiagramFull | null> {
    if (!authStore.isAuthenticated) return null

    // Validate spec size before sending
    const specJson = JSON.stringify(spec)
    const specSizeKB = new Blob([specJson]).size / 1024
    if (specSizeKB > SAVE.MAX_SPEC_SIZE_KB) {
      console.error(
        `[SavedDiagrams] Spec too large: ${specSizeKB.toFixed(1)}KB > ${SAVE.MAX_SPEC_SIZE_KB}KB`
      )
      error.value = `Diagram data too large (${specSizeKB.toFixed(0)}KB). Maximum is ${SAVE.MAX_SPEC_SIZE_KB}KB.`
      return null
    }

    // Validate thumbnail size if provided
    if (thumbnail && thumbnail.length > MAX_THUMBNAIL_SIZE) {
      console.warn(`[SavedDiagrams] Thumbnail too large (${thumbnail.length} chars), skipping`)
      thumbnail = null // Skip thumbnail rather than fail
    }

    try {
      const response = await authFetch('/api/diagrams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          diagram_type: diagramType,
          spec,
          language,
          thumbnail,
        }),
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后保存图表')
          return null
        }
        if (response.status === 403) {
          const apiDetail = await readDiagramApiErrorDetail(response)
          error.value = diagramLimitMessage(maxDiagrams.value, apiDetail)
          notifyDiagramLimitReached(maxDiagrams.value, apiDetail)
          return null
        }
        const apiDetail = await readDiagramApiErrorDetail(response)
        const message = apiDetail || `Failed to save diagram: ${response.status}`
        error.value = message
        console.error('[SavedDiagrams] Save error:', message)
        return null
      }

      const saved: SavedDiagramFull = await response.json()
      applyThinkingCoinMutation(extractThinkingCoinsFooter(saved as unknown as Record<string, unknown>))

      // Add to local list
      diagrams.value.unshift({
        id: saved.id,
        title: saved.title,
        diagram_type: saved.diagram_type,
        thumbnail: saved.thumbnail,
        updated_at: saved.updated_at,
        is_pinned: false,
      })
      total.value++

      return saved
    } catch (e) {
      console.error('[SavedDiagrams] Save error:', e)
      return null
    }
  }

  async function updateDiagram(
    diagramId: string,
    updates: {
      title?: string
      spec?: Record<string, unknown>
      thumbnail?: string
      edit_count?: number
    }
  ): Promise<boolean> {
    if (!authStore.isAuthenticated) return false

    // Validate spec size if provided
    if (updates.spec) {
      const specJson = JSON.stringify(updates.spec)
      const specSizeKB = new Blob([specJson]).size / 1024
      if (specSizeKB > SAVE.MAX_SPEC_SIZE_KB) {
        console.error(
          `[SavedDiagrams] Spec too large: ${specSizeKB.toFixed(1)}KB > ${SAVE.MAX_SPEC_SIZE_KB}KB`
        )
        error.value = `Diagram data too large (${specSizeKB.toFixed(0)}KB). Maximum is ${SAVE.MAX_SPEC_SIZE_KB}KB.`
        return false
      }
    }

    // Validate thumbnail size if provided
    if (updates.thumbnail && updates.thumbnail.length > MAX_THUMBNAIL_SIZE) {
      console.warn(
        `[SavedDiagrams] Thumbnail too large (${updates.thumbnail.length} chars), skipping`
      )
      delete updates.thumbnail // Skip thumbnail rather than fail
    }

    try {
      const response = await authFetch(`/api/diagrams/${diagramId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后更新图表')
          return false
        }
        const apiDetail = await readDiagramApiErrorDetail(response)
        const message = apiDetail || `Failed to update diagram: ${response.status}`
        error.value = message
        console.error('[SavedDiagrams] Update error:', message)
        return false
      }

      const updated: SavedDiagramFull = await response.json()
      applyThinkingCoinMutation(extractThinkingCoinsFooter(updated as unknown as Record<string, unknown>))

      // Update local list
      const index = diagrams.value.findIndex((d) => d.id === diagramId)
      if (index !== -1) {
        diagrams.value[index] = {
          id: updated.id,
          title: updated.title,
          diagram_type: updated.diagram_type,
          thumbnail: updated.thumbnail,
          updated_at: updated.updated_at,
          is_pinned: updated.is_pinned ?? diagrams.value[index].is_pinned,
        }
      }

      return true
    } catch (e) {
      console.error('[SavedDiagrams] Update error:', e)
      return false
    }
  }

  async function deleteDiagram(diagramId: string): Promise<boolean> {
    if (!authStore.isAuthenticated) return false

    try {
      const response = await authFetch(`/api/diagrams/${diagramId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后删除图表')
          return false
        }
        // If diagram doesn't exist (404), still remove from local list
        // This handles race conditions where diagram was already deleted
        if (response.status === 404) {
          console.warn(
            `[SavedDiagrams] Diagram ${diagramId} not found (404), removing from local list`
          )
          diagrams.value = diagrams.value.filter((d) => d.id !== diagramId)
          total.value--
          if (currentDiagramId.value === diagramId) {
            currentDiagramId.value = null
          }
          // Clear active diagram if it's the one being deleted
          if (activeDiagramId.value === diagramId) {
            activeDiagramId.value = null
          }
          return true // Consider it successful since it's already gone
        }
        throw new Error(`Failed to delete diagram: ${response.status}`)
      }

      // Remove from local list
      diagrams.value = diagrams.value.filter((d) => d.id !== diagramId)
      total.value--

      // Clear current if deleted
      if (currentDiagramId.value === diagramId) {
        currentDiagramId.value = null
      }

      // Clear active diagram if it's the one being deleted
      if (activeDiagramId.value === diagramId) {
        activeDiagramId.value = null
      }

      return true
    } catch (e) {
      console.error('[SavedDiagrams] Delete error:', e)
      return false
    }
  }

  async function duplicateDiagram(diagramId: string): Promise<SavedDiagramFull | null> {
    if (!authStore.isAuthenticated) return null

    try {
      const response = await authFetch(`/api/diagrams/${diagramId}/duplicate`, {
        method: 'POST',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录')
          return null
        }
        if (response.status === 403) {
          let apiDetail = ''
          try {
            const payload = await response.json()
            if (typeof payload.detail === 'string') {
              apiDetail = payload.detail
            }
          } catch {
            apiDetail = ''
          }
          error.value = diagramLimitMessage(maxDiagrams.value, apiDetail)
          notifyDiagramLimitReached(maxDiagrams.value, apiDetail)
          return null
        }
        throw new Error(`Failed to duplicate diagram: ${response.status}`)
      }

      const duplicated: SavedDiagramFull = await response.json()

      // Add to local list
      diagrams.value.unshift({
        id: duplicated.id,
        title: duplicated.title,
        diagram_type: duplicated.diagram_type,
        thumbnail: duplicated.thumbnail,
        updated_at: duplicated.updated_at,
        is_pinned: false,
      })
      total.value++

      return duplicated
    } catch (e) {
      console.error('[SavedDiagrams] Duplicate error:', e)
      return null
    }
  }

  async function pinDiagram(diagramId: string, pinned: boolean): Promise<boolean> {
    if (!authStore.isAuthenticated) return false

    try {
      const response = await authFetch(`/api/diagrams/${diagramId}/pin?pinned=${pinned}`, {
        method: 'POST',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录')
          return false
        }
        throw new Error(`Failed to ${pinned ? 'pin' : 'unpin'} diagram: ${response.status}`)
      }

      // Update local list - move pinned to front, unpinned back to natural position
      const index = diagrams.value.findIndex((d) => d.id === diagramId)
      if (index !== -1) {
        diagrams.value[index].is_pinned = pinned
        // Re-sort: pinned first, then by updated_at
        diagrams.value.sort((a, b) => {
          if (a.is_pinned !== b.is_pinned) {
            return a.is_pinned ? -1 : 1
          }
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        })
      }

      return true
    } catch (e) {
      console.error('[SavedDiagrams] Pin error:', e)
      return false
    }
  }

  function setCurrentDiagram(diagramId: string | null): void {
    currentDiagramId.value = diagramId
  }

  /**
   * Set the active diagram ID (diagram currently open in canvas)
   * Call this when loading a diagram from library into canvas
   */
  function setActiveDiagram(diagramId: string | null): void {
    activeDiagramId.value = diagramId
  }

  /**
   * Clear the active diagram (when creating new diagram in canvas)
   */
  function clearActiveDiagram(): void {
    activeDiagramId.value = null
  }

  /**
   * Auto-save diagram logic:
   * - If diagram is already saved (activeDiagramId set): update existing
   * - If new diagram and slots available: save as new
   * - If new diagram and slots full: skip (return skipped status)
   * - If new diagram is empty/unmodified: skip (return skipped status)
   *
   * @param title - Diagram title
   * @param diagramType - Type of diagram
   * @param spec - Diagram spec data
   * @param language - Language code (default 'zh')
   * @param thumbnail - Optional thumbnail
   * @returns AutoSaveResult with action taken
   */
  async function autoSaveDiagram(
    title: string,
    diagramType: string,
    spec: Record<string, unknown>,
    language: string = 'zh',
    thumbnail: string | null = null,
    editCount: number = 0
  ): Promise<AutoSaveResult> {
    if (!authStore.isAuthenticated) {
      return { success: false, action: 'skipped', error: 'Not authenticated' }
    }

    isAutoSaving.value = true

    try {
      // Case 1: Diagram is already saved - update it
      if (activeDiagramId.value !== null) {
        const updates: {
          title: string
          spec: Record<string, unknown>
          thumbnail?: string
          edit_count?: number
        } = { title, spec, thumbnail: thumbnail || undefined }
        if (editCount > 0) {
          updates.edit_count = editCount
        }
        const updated = await updateDiagram(activeDiagramId.value, updates)

        if (updated) {
          return { success: true, action: 'updated', diagramId: activeDiagramId.value }
        } else {
          return { success: false, action: 'error', error: 'Failed to update diagram' }
        }
      }

      // Case 2: New diagram - check if it's empty/unmodified
      if (isDiagramEmpty(spec, diagramType as DiagramType)) {
        // Empty diagram - skip auto-save silently
        return { success: false, action: 'skipped', error: 'Diagram is empty/unmodified' }
      }

      // Case 3: New diagram - check if we have slots
      if (!canSaveMore.value) {
        // Slots full - skip auto-save silently
        return { success: false, action: 'skipped', error: 'No available slots' }
      }

      // Case 4: New diagram with available slots - save it
      const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)

      if (saved) {
        activeDiagramId.value = saved.id
        usePanelsStore().migrateNodePaletteSessionToSavedDiagram(diagramType, saved.id)
        if (diagramType === 'mindmap' || diagramType === 'mind_map') {
          usePanelsStore().migrateConceptParkingLotSessionToSavedDiagram(saved.id)
        }
        return { success: true, action: 'saved', diagramId: saved.id }
      } else {
        return { success: false, action: 'error', error: error.value || 'Failed to save diagram' }
      }
    } catch (e) {
      console.error('[SavedDiagrams] Auto-save error:', e)
      return {
        success: false,
        action: 'error',
        error: e instanceof Error ? e.message : 'Auto-save failed',
      }
    } finally {
      isAutoSaving.value = false
    }
  }

  /**
   * Save current diagram to database before it gets replaced (e.g. model switch).
   * Preserves learning sheet state (is_learning_sheet, hiddenAnswers) and other user edits.
   * Call this before loadFromSpec when replacing diagram content.
   */
  async function saveCurrentDiagramBeforeReplace(): Promise<void> {
    const diagramStore = useDiagramStore()
    const llmResultsStore = useLLMResultsStore()
    if (!authStore.isAuthenticated || !diagramStore.type || !diagramStore.data) return

    let spec = diagramStore.getSpecForSave()
    if (!spec) return

    llmResultsStore.updateCurrentModelSpec(spec)
    const persisted = llmResultsStore.getResultsForPersistence()
    if (persisted) {
      const withLlm = { ...spec, llm_results: persisted }
      const sizeKB = new Blob([JSON.stringify(withLlm)]).size / 1024
      spec = sizeKB <= SAVE.MAX_SPEC_SIZE_KB ? withLlm : spec
    }

    const title = resolveDiagramTitleForSave(
      diagramStore.effectiveTitle,
      diagramStore.type,
      uiStore.language
    )

    try {
      await autoSaveDiagram(
        title,
        diagramStore.type,
        spec,
        uiStore.language,
        null,
        diagramStore.sessionEditCount
      )
      diagramStore.resetSessionEditCount()
    } catch (e) {
      console.error('[SavedDiagrams] Save-before-replace error:', e)
    }
  }

  /**
   * Manual save with slot management
   * Unlike auto-save, this will return an error if slots are full
   * so the UI can show a modal to let user delete a diagram first
   *
   * @returns Result with needsSlotClear flag if slots are full
   */
  async function manualSaveDiagram(
    title: string,
    diagramType: string,
    spec: Record<string, unknown>,
    language: string = 'zh',
    thumbnail: string | null = null
  ): Promise<AutoSaveResult & { needsSlotClear?: boolean }> {
    const llmResultsStore = useLLMResultsStore()
    if (!authStore.isAuthenticated) {
      return { success: false, action: 'error', error: 'Please login to save diagrams' }
    }

    // If already saved, just update
    if (activeDiagramId.value !== null) {
      const updated = await updateDiagram(activeDiagramId.value, {
        title,
        spec,
        thumbnail: thumbnail || undefined,
      })

      if (updated) {
        llmResultsStore.updateCurrentModelSpec(spec)
        return { success: true, action: 'updated', diagramId: activeDiagramId.value }
      } else {
        return { success: false, action: 'error', error: 'Failed to update diagram' }
      }
    }

    // New diagram - check slots
    if (!canSaveMore.value) {
      notify.warning(
        i18n.global.t('auth.diagramLimitReached', { max: maxDiagrams.value }) as string
      )
      return {
        success: false,
        action: 'skipped',
        error: 'Diagram slots full',
        needsSlotClear: true,
      }
    }

    // Save new diagram
    const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)

    if (saved) {
      activeDiagramId.value = saved.id
      llmResultsStore.updateCurrentModelSpec(spec)
      usePanelsStore().migrateNodePaletteSessionToSavedDiagram(diagramType, saved.id)
      if (diagramType === 'mindmap' || diagramType === 'mind_map') {
        usePanelsStore().migrateConceptParkingLotSessionToSavedDiagram(saved.id)
      }
      return { success: true, action: 'saved', diagramId: saved.id }
    } else {
      return { success: false, action: 'error', error: error.value || 'Failed to save diagram' }
    }
  }

  /**
   * Delete a diagram and then save the current one
   * Used when slots are full and user selects a diagram to delete
   */
  async function deleteAndSave(
    diagramIdToDelete: string,
    title: string,
    diagramType: string,
    spec: Record<string, unknown>,
    language: string = 'zh',
    thumbnail: string | null = null
  ): Promise<AutoSaveResult> {
    const llmResultsStore = useLLMResultsStore()
    // First delete the selected diagram
    const deleted = await deleteDiagram(diagramIdToDelete)
    if (!deleted) {
      return { success: false, action: 'error', error: 'Failed to delete diagram' }
    }

    // Now save the new one
    const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)
    if (saved) {
      activeDiagramId.value = saved.id
      llmResultsStore.updateCurrentModelSpec(spec)
      usePanelsStore().migrateNodePaletteSessionToSavedDiagram(diagramType, saved.id)
      if (diagramType === 'mindmap' || diagramType === 'mind_map') {
        usePanelsStore().migrateConceptParkingLotSessionToSavedDiagram(saved.id)
      }
      return { success: true, action: 'saved', diagramId: saved.id }
    } else {
      return { success: false, action: 'error', error: error.value || 'Failed to save diagram' }
    }
  }

  function reset(): void {
    diagrams.value = []
    folders.value = []
    foldersLoadFailed.value = false
    total.value = 0
    isLoading.value = false
    error.value = null
    currentDiagramId.value = null
    activeDiagramId.value = null
    isAutoSaving.value = false
    diagramDetailCache.clear()
  }

  return {
    // State
    diagrams,
    folders,
    foldersLoadFailed,
    total,
    maxDiagrams,
    isLoading,
    error,
    currentDiagramId,
    activeDiagramId,
    isAutoSaving,

    // Getters
    hasSaveLimit,
    canSaveMore,
    remainingSlots,
    isActiveDiagramSaved,
    isSlotsFullyUsed,

    // Actions
    fetchDiagrams,
    createFolder,
    renameFolder,
    deleteFolder,
    moveDiagramToFolder,
    stopDiagramOnlineCollab,
    getDiagram,
    getCachedDiagram,
    getCachedDiagramSpec,
    prefetchDiagramSpecs,
    saveDiagram,
    updateDiagram,
    deleteDiagram,
    duplicateDiagram,
    pinDiagram,
    setCurrentDiagram,
    setActiveDiagram,
    clearActiveDiagram,
    autoSaveDiagram,
    saveCurrentDiagramBeforeReplace,
    manualSaveDiagram,
    deleteAndSave,
    reset,
  }
})
