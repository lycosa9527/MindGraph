/**
 * Concept Map Relationship Store - transient state for AI-generated label picker
 *
 * When user drags concepts to create a link, catapult API streams relationship labels.
 * Store holds all labels, supports pagination (5 per page) with - and = keys.
 *
 * Kept separate from the diagram store because:
 * - Frequently updated (on each new link, streaming)
 * - Frequently cleared (pane click, select, edit, reset)
 * - Concept-map-specific UI state, not diagram data
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { authFetch } from '@/utils/api'

import { RELATIONSHIP_LABELS_CLEANUP } from '@/composables/nodePalette/constants'

const LABELS_PER_PAGE = 5

export const useConceptMapRelationshipStore = defineStore(
  'conceptMapRelationship',
  () => {
    /** connectionId -> all labels (streamed + appended from next_batch) */
    const allLabels = ref<Record<string, string[]>>({})
    /** connectionId -> current page index (0-based) */
    const page = ref<Record<string, number>>({})
    /** AbortController for in-flight stream; abort when user clicks canvas (clearAll) */
    const streamAbortController = ref<AbortController | null>(null)

    /** connectionId -> list of relationship label options (legacy: first 5 for backward compat) */
    const options = computed(() => {
      const out: Record<string, string[]> = {}
      for (const [connId, labels] of Object.entries(allLabels.value)) {
        const p = page.value[connId] ?? 0
        const start = p * LABELS_PER_PAGE
        out[connId] = labels.slice(start, start + LABELS_PER_PAGE)
      }
      return out
    })

    /** First connection with options, for the bottom bar picker */
    const activeEntry = computed((): [string, string[]] | null => {
      const entries = Object.entries(options.value)
      return entries.length > 0 ? entries[0] : null
    })

    /** All labels for active connection (for pagination) */
    const activeAllLabels = computed((): string[] => {
      const entry = activeEntry.value
      if (!entry) return []
      return allLabels.value[entry[0]] ?? []
    })

    /** Current page for active connection */
    const activePage = computed((): number => {
      const entry = activeEntry.value
      if (!entry) return 0
      return page.value[entry[0]] ?? 0
    })

    /** Total pages for active connection */
    const activeTotalPages = computed((): number => {
      const n = activeAllLabels.value.length
      return n <= 0 ? 0 : Math.ceil(n / LABELS_PER_PAGE)
    })

    /** Whether we can go to previous page */
    const canPrevPage = computed((): boolean => activePage.value > 0)

    /** Whether we can go to next page or fetch more (show = when we have options) */
    const canNextPage = computed((): boolean => activeTotalPages.value > 0)

    function setOptions(connectionId: string, labels: string[]): void {
      allLabels.value = { [connectionId]: labels }
      page.value = { [connectionId]: 0 }
    }

    /** Append labels (from next_batch), filter duplicates */
    function appendLabels(connectionId: string, newLabels: string[]): void {
      const existing = allLabels.value[connectionId] ?? []
      const seen = new Set(existing.map((l) => l.toLowerCase().trim()))
      const added: string[] = []
      for (const l of newLabels) {
        const k = l.toLowerCase().trim()
        if (!seen.has(k)) {
          seen.add(k)
          added.push(l)
        }
      }
      if (added.length > 0) {
        allLabels.value = {
          ...allLabels.value,
          [connectionId]: [...existing, ...added],
        }
      }
    }

    function abortStream(): void {
      if (streamAbortController.value) {
        streamAbortController.value.abort()
        streamAbortController.value = null
      }
    }

    function setStreamAbortController(controller: AbortController | null): void {
      streamAbortController.value = controller
    }

    function clearConnection(connectionId: string): void {
      if (connectionId in allLabels.value) abortStream()
      const nextLabels = { ...allLabels.value }
      const nextPage = { ...page.value }
      delete nextLabels[connectionId]
      delete nextPage[connectionId]
      allLabels.value = nextLabels
      page.value = nextPage
      cleanupBackendSessions([connectionId])
    }

    function clearAll(): void {
      abortStream()
      const ids = Object.keys(allLabels.value)
      allLabels.value = {}
      page.value = {}
      if (ids.length > 0) {
        cleanupBackendSessions(ids)
      }
    }

    function cleanupBackendSessions(connectionIds: string[]): void {
      if (connectionIds.length === 0) return
      authFetch(RELATIONSHIP_LABELS_CLEANUP, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_ids: connectionIds }),
      }).catch(() => {
        // Fire-and-forget; ignore errors (user may be offline)
      })
    }

    function prevPage(connectionId: string): boolean {
      const p = page.value[connectionId] ?? 0
      if (p <= 0) return false
      page.value = { ...page.value, [connectionId]: p - 1 }
      return true
    }

    function nextPage(connectionId: string): boolean {
      const labels = allLabels.value[connectionId] ?? []
      const p = page.value[connectionId] ?? 0
      const totalPages = Math.ceil(labels.length / LABELS_PER_PAGE)
      if (p >= totalPages - 1) return false
      page.value = { ...page.value, [connectionId]: p + 1 }
      return true
    }

    /** Get global index of option at local index on current page */
    function getGlobalIndex(connectionId: string, localIndex: number): number {
      const p = page.value[connectionId] ?? 0
      return p * LABELS_PER_PAGE + localIndex
    }

    return {
      options,
      allLabels,
      page,
      activeEntry,
      setStreamAbortController,
      activeAllLabels,
      activePage,
      activeTotalPages,
      canPrevPage,
      canNextPage,
      setOptions,
      appendLabels,
      clearConnection,
      clearAll,
      prevPage,
      nextPage,
      getGlobalIndex,
    }
  }
)
