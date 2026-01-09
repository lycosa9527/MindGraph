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

import { useAuthStore } from './auth'

// Security constants - must match backend limits
const MAX_SPEC_SIZE_KB = 500  // Backend limit from DIAGRAM_MAX_SPEC_SIZE_KB
const MAX_THUMBNAIL_SIZE = 150000  // Max base64 chars (~100KB decoded)

// Types
export interface SavedDiagram {
  id: string  // UUID
  title: string
  diagram_type: string
  thumbnail: string | null
  updated_at: string // ISO date string
  is_pinned: boolean
}

export interface SavedDiagramFull extends SavedDiagram {
  spec: Record<string, unknown>
  language: string
  created_at: string
}

// Type for diagram IDs (UUID strings)
export type DiagramId = string

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
  const total = ref(0)
  const maxDiagrams = ref(20)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentDiagramId = ref<string | null>(null)
  
  // Active diagram tracking - tracks if current canvas diagram is saved to library
  const activeDiagramId = ref<string | null>(null)
  const isAutoSaving = ref(false)

  // Getters
  const authStore = useAuthStore()
  const canSaveMore = computed(() => diagrams.value.length < maxDiagrams.value)
  const remainingSlots = computed(() => maxDiagrams.value - diagrams.value.length)
  const isActiveDiagramSaved = computed(() => activeDiagramId.value !== null)
  const isSlotsFullyUsed = computed(() => diagrams.value.length >= maxDiagrams.value)

  // Actions
  async function fetchDiagrams(page: number = 1, pageSize: number = 50): Promise<boolean> {
    if (!authStore.isAuthenticated) {
      diagrams.value = []
      return false
    }

    isLoading.value = true
    error.value = null

    try {
      // Use credentials (token in httpOnly cookie)
      const response = await fetch(`/api/diagrams?page=${page}&page_size=${pageSize}`, {
        credentials: 'same-origin',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后查看图表')
          return false
        }
        throw new Error(`Failed to fetch diagrams: ${response.status}`)
      }

      const data: DiagramListResponse = await response.json()
      diagrams.value = data.diagrams
      total.value = data.total
      maxDiagrams.value = data.max_diagrams
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load diagrams'
      console.error('[SavedDiagrams] Fetch error:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function getDiagram(diagramId: string): Promise<SavedDiagramFull | null> {
    if (!authStore.isAuthenticated) return null

    try {
      const response = await fetch(`/api/diagrams/${diagramId}`, {
        credentials: 'same-origin',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录')
          return null
        }
        throw new Error(`Failed to fetch diagram: ${response.status}`)
      }

      return await response.json()
    } catch (e) {
      console.error('[SavedDiagrams] Get diagram error:', e)
      return null
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
    if (specSizeKB > MAX_SPEC_SIZE_KB) {
      console.error(`[SavedDiagrams] Spec too large: ${specSizeKB.toFixed(1)}KB > ${MAX_SPEC_SIZE_KB}KB`)
      error.value = `Diagram data too large (${specSizeKB.toFixed(0)}KB). Maximum is ${MAX_SPEC_SIZE_KB}KB.`
      return null
    }

    // Validate thumbnail size if provided
    if (thumbnail && thumbnail.length > MAX_THUMBNAIL_SIZE) {
      console.warn(`[SavedDiagrams] Thumbnail too large (${thumbnail.length} chars), skipping`)
      thumbnail = null  // Skip thumbnail rather than fail
    }

    try {
      const response = await fetch('/api/diagrams', {
        method: 'POST',
        credentials: 'same-origin',
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
          error.value = 'Diagram limit reached'
          return null
        }
        throw new Error(`Failed to save diagram: ${response.status}`)
      }

      const saved: SavedDiagramFull = await response.json()
      
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
    updates: { title?: string; spec?: Record<string, unknown>; thumbnail?: string }
  ): Promise<boolean> {
    if (!authStore.isAuthenticated) return false

    // Validate spec size if provided
    if (updates.spec) {
      const specJson = JSON.stringify(updates.spec)
      const specSizeKB = new Blob([specJson]).size / 1024
      if (specSizeKB > MAX_SPEC_SIZE_KB) {
        console.error(`[SavedDiagrams] Spec too large: ${specSizeKB.toFixed(1)}KB > ${MAX_SPEC_SIZE_KB}KB`)
        error.value = `Diagram data too large (${specSizeKB.toFixed(0)}KB). Maximum is ${MAX_SPEC_SIZE_KB}KB.`
        return false
      }
    }

    // Validate thumbnail size if provided
    if (updates.thumbnail && updates.thumbnail.length > MAX_THUMBNAIL_SIZE) {
      console.warn(`[SavedDiagrams] Thumbnail too large (${updates.thumbnail.length} chars), skipping`)
      delete updates.thumbnail  // Skip thumbnail rather than fail
    }

    try {
      const response = await fetch(`/api/diagrams/${diagramId}`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后更新图表')
          return false
        }
        throw new Error(`Failed to update diagram: ${response.status}`)
      }

      const updated: SavedDiagramFull = await response.json()
      
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
      const response = await fetch(`/api/diagrams/${diagramId}`, {
        method: 'DELETE',
        credentials: 'same-origin',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后删除图表')
          return false
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

      return true
    } catch (e) {
      console.error('[SavedDiagrams] Delete error:', e)
      return false
    }
  }

  async function duplicateDiagram(diagramId: string): Promise<SavedDiagramFull | null> {
    if (!authStore.isAuthenticated) return null

    try {
      const response = await fetch(`/api/diagrams/${diagramId}/duplicate`, {
        method: 'POST',
        credentials: 'same-origin',
      })

      if (!response.ok) {
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录')
          return null
        }
        if (response.status === 403) {
          error.value = 'Diagram limit reached'
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
      const response = await fetch(`/api/diagrams/${diagramId}/pin?pinned=${pinned}`, {
        method: 'POST',
        credentials: 'same-origin',
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
    thumbnail: string | null = null
  ): Promise<AutoSaveResult> {
    if (!authStore.isAuthenticated) {
      return { success: false, action: 'skipped', error: 'Not authenticated' }
    }

    isAutoSaving.value = true

    try {
      // Case 1: Diagram is already saved - update it
      if (activeDiagramId.value !== null) {
        const updated = await updateDiagram(activeDiagramId.value, {
          title,
          spec,
          thumbnail: thumbnail || undefined,
        })
        
        if (updated) {
          return { success: true, action: 'updated', diagramId: activeDiagramId.value }
        } else {
          return { success: false, action: 'error', error: 'Failed to update diagram' }
        }
      }

      // Case 2: New diagram - check if we have slots
      if (!canSaveMore.value) {
        // Slots full - skip auto-save silently
        return { success: false, action: 'skipped', error: 'No available slots' }
      }

      // Case 3: New diagram with available slots - save it
      const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)
      
      if (saved) {
        // Track this as the active diagram
        activeDiagramId.value = saved.id
        return { success: true, action: 'saved', diagramId: saved.id }
      } else {
        return { success: false, action: 'error', error: error.value || 'Failed to save diagram' }
      }
    } catch (e) {
      console.error('[SavedDiagrams] Auto-save error:', e)
      return { 
        success: false, 
        action: 'error', 
        error: e instanceof Error ? e.message : 'Auto-save failed' 
      }
    } finally {
      isAutoSaving.value = false
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
        return { success: true, action: 'updated', diagramId: activeDiagramId.value }
      } else {
        return { success: false, action: 'error', error: 'Failed to update diagram' }
      }
    }

    // New diagram - check slots
    if (!canSaveMore.value) {
      return { 
        success: false, 
        action: 'skipped', 
        error: 'Diagram slots full',
        needsSlotClear: true 
      }
    }

    // Save new diagram
    const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)
    
    if (saved) {
      activeDiagramId.value = saved.id
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
    // First delete the selected diagram
    const deleted = await deleteDiagram(diagramIdToDelete)
    if (!deleted) {
      return { success: false, action: 'error', error: 'Failed to delete diagram' }
    }

    // Now save the new one
    const saved = await saveDiagram(title, diagramType, spec, language, thumbnail)
    if (saved) {
      activeDiagramId.value = saved.id
      return { success: true, action: 'saved', diagramId: saved.id }
    } else {
      return { success: false, action: 'error', error: error.value || 'Failed to save diagram' }
    }
  }

  function reset(): void {
    diagrams.value = []
    total.value = 0
    isLoading.value = false
    error.value = null
    currentDiagramId.value = null
    activeDiagramId.value = null
    isAutoSaving.value = false
  }

  return {
    // State
    diagrams,
    total,
    maxDiagrams,
    isLoading,
    error,
    currentDiagramId,
    activeDiagramId,
    isAutoSaving,

    // Getters
    canSaveMore,
    remainingSlots,
    isActiveDiagramSaved,
    isSlotsFullyUsed,

    // Actions
    fetchDiagrams,
    getDiagram,
    saveDiagram,
    updateDiagram,
    deleteDiagram,
    duplicateDiagram,
    pinDiagram,
    setCurrentDiagram,
    setActiveDiagram,
    clearActiveDiagram,
    autoSaveDiagram,
    manualSaveDiagram,
    deleteAndSave,
    reset,
  }
})
