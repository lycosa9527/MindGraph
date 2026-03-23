/**
 * Inline Recommendations Store - transient state for diagram auto-completion
 *
 * Trigger: User fixes topic, double-clicks node to edit, then presses Tab.
 * Store holds options, supports pagination.
 *
 * Designed for frequent updates: topic change invalidates all, coordinator
 * dispatches events to store actions.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { INLINE_RECOMMENDATIONS_CLEANUP } from '@/composables/nodePalette/constants'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'

const OPTIONS_PER_PAGE = 5

export const useInlineRecommendationsStore = defineStore('inlineRecommendations', () => {
  /** nodeId -> all recommendations (streamed + appended from next_batch) */
  const allOptions = ref<Record<string, string[]>>({})
  /** nodeId -> current page index (0-based) */
  const page = ref<Record<string, number>>({})
  /** Currently active node for picker */
  const activeNodeId = ref<string | null>(null)
  /** Topic defined + diagram supports inline recs */
  const isReady = ref(false)
  /** nodeIds currently generating */
  const generatingNodeIds = ref<Set<string>>(new Set())
  /** nodeIds currently fetching next batch */
  const fetchingNextBatchNodeIds = ref<Set<string>>(new Set())
  /** Hash of last topic for change detection */
  const lastTopicHash = ref('')
  /** AbortController for in-flight stream */
  const streamAbortController = ref<AbortController | null>(null)
  /**
   * Tab rec badge (AIModelSelector): `requesting` = HTTP wait (blue ring),
   * `streaming` = SSE tokens (green ring), `idle` = solid green (ready or finished).
   */
  const streamPhase = ref<'idle' | 'requesting' | 'streaming'>('idle')

  /** nodeId -> options for current page (first 5) */
  const options = computed(() => {
    const out: Record<string, string[]> = {}
    for (const [nid, opts] of Object.entries(allOptions.value)) {
      const p = page.value[nid] ?? 0
      const start = p * OPTIONS_PER_PAGE
      out[nid] = opts.slice(start, start + OPTIONS_PER_PAGE)
    }
    return out
  })

  /** Options for active node */
  const activeOptions = computed((): string[] => {
    const nid = activeNodeId.value
    if (!nid) return []
    return options.value[nid] ?? []
  })

  /** [nodeId, options[]] for picker - same pattern as concept map activeEntry */
  const activeEntry = computed((): [string, string[]] | null => {
    const nid = activeNodeId.value
    if (!nid) return null
    const opts = options.value[nid] ?? []
    return opts.length > 0 ? [nid, opts] : null
  })

  /** All options for active node (for pagination) */
  const activeAllOptions = computed((): string[] => {
    const nid = activeNodeId.value
    if (!nid) return []
    return allOptions.value[nid] ?? []
  })

  /** Current page for active node */
  const activePage = computed((): number => {
    const nid = activeNodeId.value
    if (!nid) return 0
    return page.value[nid] ?? 0
  })

  /** Total pages for active node */
  const activeTotalPages = computed((): number => {
    const n = activeAllOptions.value.length
    return n <= 0 ? 0 : Math.ceil(n / OPTIONS_PER_PAGE)
  })

  const canPrevPage = computed((): boolean => activePage.value > 0)
  const canNextPage = computed((): boolean => activeTotalPages.value > 0)

  function _hashTopic(topic: string): string {
    return `${topic.length}:${topic.slice(0, 50)}`
  }

  /**
   * Call when topic node text changes.
   * topicValid: from coordinator (extractMainTopic + isPlaceholderText + diagram type check)
   */
  function onTopicUpdated(topic: string, topicValid: boolean): void {
    isReady.value = topicValid

    const newHash = _hashTopic(topic)
    if (lastTopicHash.value !== newHash) {
      lastTopicHash.value = newHash
      invalidateAll()
    }
  }

  function setStreamPhase(phase: 'idle' | 'requesting' | 'streaming'): void {
    streamPhase.value = phase
  }

  function invalidateAll(): void {
    abortStream()
    streamPhase.value = 'idle'
    const ids = Object.keys(allOptions.value)
    allOptions.value = {}
    page.value = {}
    activeNodeId.value = null
    generatingNodeIds.value = new Set()
    fetchingNextBatchNodeIds.value = new Set()
    if (ids.length > 0) {
      cleanupBackendSessions(ids)
    }
  }

  function invalidateForNode(nodeId: string): void {
    if (nodeId in allOptions.value) {
      abortStream()
      streamPhase.value = 'idle'
    }
    const next = { ...allOptions.value }
    const nextPage = { ...page.value }
    delete next[nodeId]
    delete nextPage[nodeId]
    allOptions.value = next
    page.value = nextPage
    if (activeNodeId.value === nodeId) {
      activeNodeId.value = null
    }
    const nextFetching = new Set(fetchingNextBatchNodeIds.value)
    nextFetching.delete(nodeId)
    fetchingNextBatchNodeIds.value = nextFetching
    cleanupBackendSessions([nodeId])
  }

  function setOptions(nodeId: string, opts: string[], preservePage = false): void {
    allOptions.value = { ...allOptions.value, [nodeId]: opts }
    if (!preservePage) {
      page.value = { ...page.value, [nodeId]: 0 }
    }
    activeNodeId.value = nodeId
  }

  function appendOptions(nodeId: string, newOpts: string[]): void {
    const existing = allOptions.value[nodeId] ?? []
    const seen = new Set(existing.map((o) => o.toLowerCase().trim()))
    const added: string[] = []
    for (const o of newOpts) {
      const k = o.toLowerCase().trim()
      if (!seen.has(k)) {
        seen.add(k)
        added.push(o)
      }
    }
    if (added.length > 0) {
      allOptions.value = {
        ...allOptions.value,
        [nodeId]: [...existing, ...added],
      }
    }
  }

  function setActive(nodeId: string | null): void {
    activeNodeId.value = nodeId
  }

  function clearActive(): void {
    activeNodeId.value = null
  }

  function setReady(ready: boolean): void {
    isReady.value = ready
  }

  function setGenerating(nodeId: string, generating: boolean): void {
    const next = new Set(generatingNodeIds.value)
    if (generating) {
      next.add(nodeId)
    } else {
      next.delete(nodeId)
    }
    generatingNodeIds.value = next
  }

  function setFetchingNextBatch(nodeId: string, fetching: boolean): void {
    const next = new Set(fetchingNextBatchNodeIds.value)
    if (fetching) {
      next.add(nodeId)
    } else {
      next.delete(nodeId)
    }
    fetchingNextBatchNodeIds.value = next
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

  function cleanupBackendSessions(nodeIds: string[]): void {
    if (nodeIds.length === 0) return
    if (!useAuthStore().isAuthenticated) return
    authFetch(INLINE_RECOMMENDATIONS_CLEANUP, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_ids: nodeIds }),
    }).catch(() => {
      // Silently ignore 401/network errors - cleanup is best-effort
    })
  }

  function prevPage(nodeId: string): boolean {
    const p = page.value[nodeId] ?? 0
    if (p <= 0) return false
    page.value = { ...page.value, [nodeId]: p - 1 }
    return true
  }

  function nextPage(nodeId: string): boolean {
    const opts = allOptions.value[nodeId] ?? []
    const p = page.value[nodeId] ?? 0
    const totalPages = Math.ceil(opts.length / OPTIONS_PER_PAGE)
    if (p >= totalPages - 1) return false
    page.value = { ...page.value, [nodeId]: p + 1 }
    return true
  }

  function getGlobalIndex(nodeId: string, localIndex: number): number {
    const p = page.value[nodeId] ?? 0
    return p * OPTIONS_PER_PAGE + localIndex
  }

  return {
    options,
    allOptions,
    page,
    activeNodeId,
    activeOptions,
    activeEntry,
    activeAllOptions,
    activePage,
    activeTotalPages,
    canPrevPage,
    canNextPage,
    isReady,
    streamPhase,
    setStreamPhase,
    generatingNodeIds,
    fetchingNextBatchNodeIds,
    lastTopicHash,
    onTopicUpdated,
    invalidateAll,
    invalidateForNode,
    setOptions,
    appendOptions,
    setActive,
    clearActive,
    setReady,
    setGenerating,
    setFetchingNextBatch,
    setStreamAbortController,
    abortStream,
    prevPage,
    nextPage,
    getGlobalIndex,
  }
})
