/**
 * useConceptMapRelationship - AI-generated relationship labels for concept map links
 *
 * Catapult-style: fires 3 LLMs concurrently, streams labels via SSE.
 * Shows first 5; user uses - and = for prev/next page. On next page when at end,
 * fetches more via next_batch and filters duplicates.
 *
 * Label agent: When a concept node's text changes, only regenerates edges with
 * empty labels—avoids overwriting user-edited or AI-generated labels.
 */
import { ref } from 'vue'

import { isPlaceholderText } from '@/composables/useAutoComplete'
import { useLanguage } from '@/composables/useLanguage'
import { useNotifications } from '@/composables/useNotifications'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'

import {
  RELATIONSHIP_LABELS_NEXT,
  RELATIONSHIP_LABELS_START,
} from './nodePalette/constants'

export const CONCEPT_MAP_GENERATING_KEY = Symbol('conceptMapRelationshipGenerating')
export const CONCEPT_MAP_OPTIONS_KEY = Symbol('conceptMapRelationshipOptions')

/** Template-default labels (from getDefaultTemplate) — safe to regenerate when concepts change */
const TEMPLATE_DEFAULT_LABELS = new Set([
  '关联',
  '包含',
  '导致',
  'related to',
  'includes',
  'causes',
])

/** Edge label is empty, placeholder, or template default—safe to regenerate */
function isLabelEmptyOrPlaceholder(label: string | undefined | null): boolean {
  if (!label || !label.trim()) return true
  const t = label.trim()
  if (
    t === '输入关系...' ||
    t === 'Enter relationship...' ||
    t.toLowerCase() === 'enter relationship...'
  ) {
    return true
  }
  return TEMPLATE_DEFAULT_LABELS.has(t) || TEMPLATE_DEFAULT_LABELS.has(t.toLowerCase())
}

async function streamRelationshipLabels(
  url: string,
  payload: Record<string, unknown>,
  onLabel: (label: string) => void,
  onError?: (msg: string) => void,
  signal?: AbortSignal
): Promise<number> {
  const response = await authFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) {
    const msg = `Request failed: ${response.status}`
    onError?.(msg)
    return 0
  }
  const reader = response.body?.getReader()
  if (!reader) {
    onError?.('No response body')
    return 0
  }
  const decoder = new TextDecoder()
  let buffer = ''
  let count = 0
  try {
    while (true) {
      if (signal?.aborted) break
      let chunk: ReadableStreamReadResult<Uint8Array>
      try {
        chunk = await reader.read()
      } catch (e) {
        if (e instanceof Error && e.name === 'AbortError') break
        throw e
      }
      const { done, value } = chunk
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6)) as {
            event?: string
            label?: string
            message?: string
          }
          if (data.event === 'label_generated' && data.label) {
            onLabel(data.label)
            count++
          } else if (data.event === 'error' && data.message) {
            onError?.(data.message)
          }
        } catch {
          // Skip malformed lines
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
  return count
}

export function useConceptMapRelationship() {
  const diagramStore = useDiagramStore()
  const relationshipStore = useConceptMapRelationshipStore()
  const llmResultsStore = useLLMResultsStore()
  const { isZh } = useLanguage()
  const notify = useNotifications()

  const generatingConnectionIds = ref<Set<string>>(new Set())
  const loadingMoreConnectionIds = ref<Set<string>>(new Set())

  function isGeneratingFor(connectionId: string): boolean {
    return generatingConnectionIds.value.has(connectionId)
  }

  function isLoadingMoreFor(connectionId: string): boolean {
    return loadingMoreConnectionIds.value.has(connectionId)
  }

  function getNodeText(nodeId: string): string {
    const nodes = diagramStore.data?.nodes ?? []
    const node = nodes.find((n) => n.id === nodeId)
    return (node?.text ?? '').trim()
  }

  function getLinkDirection(connectionId: string): string {
    const conn = diagramStore.data?.connections?.find((c) => c.id === connectionId)
    const dir = conn?.arrowheadDirection ?? 'none'
    if (dir === 'target') return 'source_to_target'
    if (dir === 'source') return 'target_to_source'
    if (dir === 'both') return 'both'
    return 'none'
  }

  async function generateRelationship(
    connectionId: string,
    sourceId: string,
    targetId: string
  ): Promise<{ success: boolean; error?: string }> {
    if (generatingConnectionIds.value.has(connectionId)) {
      return { success: false, error: 'Already generating' }
    }

    const conceptA = getNodeText(sourceId)
    const conceptB = getNodeText(targetId)

    if (isPlaceholderText(conceptA) || isPlaceholderText(conceptB)) {
      return { success: false, error: 'Placeholder text' }
    }

    generatingConnectionIds.value = new Set([...generatingConnectionIds.value, connectionId])
    const topic = diagramStore.getTopicNodeText() || ''
    const language = isZh.value ? 'zh' : 'en'
    const linkDirection = getLinkDirection(connectionId)

    const payload = {
      session_id: connectionId,
      concept_a: conceptA,
      concept_b: conceptB,
      topic,
      link_direction: linkDirection,
      language,
    }

    try {
      const controller = new AbortController()
      relationshipStore.setStreamAbortController(controller)
      const labels: string[] = []
      const onLabel = (label: string) => {
        labels.push(label)
        if (labels.length === 1) {
          diagramStore.updateConnectionLabel(connectionId, label)
          diagramStore.pushHistory('AI relationship')
        }
        relationshipStore.setOptions(connectionId, labels, labels.length > 1)
      }
      const onError = (msg: string) => {
        const title = isZh.value ? '关系生成失败' : 'Relationship generation failed'
        notify.error(`${title}: ${msg}`)
      }

      const count = await streamRelationshipLabels(
        RELATIONSHIP_LABELS_START,
        payload,
        onLabel,
        onError,
        controller.signal
      )

      const connStillExists = diagramStore.data?.connections?.some((c) => c.id === connectionId)
      if (!connStillExists) {
        return { success: false, error: 'Connection deleted' }
      }

      if (count > 0) {
        return { success: true }
      }
      return { success: false, error: 'No labels generated' }
    } catch (error) {
      const isAbort = error instanceof Error && error.name === 'AbortError'
      if (isAbort) return { success: false, error: 'Aborted' }
      const errMsg = error instanceof Error ? error.message : 'Unknown error'
      const title = isZh.value ? '关系生成失败' : 'Relationship generation failed'
      notify.error(`${title}: ${errMsg}`)
      return { success: false, error: errMsg }
    } finally {
      relationshipStore.setStreamAbortController(null)
      generatingConnectionIds.value = new Set(
        [...generatingConnectionIds.value].filter((id) => id !== connectionId)
      )
    }
  }

  /** Fetch next batch when user presses = and we're at the end of current labels */
  async function fetchNextBatch(connectionId: string): Promise<boolean> {
    if (loadingMoreConnectionIds.value.has(connectionId)) return false

    const conn = diagramStore.data?.connections?.find((c) => c.id === connectionId)
    if (!conn) return false

    const conceptA = getNodeText(conn.source)
    const conceptB = getNodeText(conn.target)
    if (isPlaceholderText(conceptA) || isPlaceholderText(conceptB)) return false

    loadingMoreConnectionIds.value = new Set([...loadingMoreConnectionIds.value, connectionId])
    const topic = diagramStore.getTopicNodeText() || ''
    const language = isZh.value ? 'zh' : 'en'
    const linkDirection = getLinkDirection(connectionId)

    const payload = {
      session_id: connectionId,
      concept_a: conceptA,
      concept_b: conceptB,
      topic,
      link_direction: linkDirection,
      language,
    }

    try {
      const controller = new AbortController()
      relationshipStore.setStreamAbortController(controller)
      const newLabels: string[] = []
      await streamRelationshipLabels(
        RELATIONSHIP_LABELS_NEXT,
        payload,
        (label) => newLabels.push(label),
        (msg) => notify.error(msg),
        controller.signal
      )
      if (newLabels.length > 0) {
        relationshipStore.appendLabels(connectionId, newLabels)
      }
      return newLabels.length > 0
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return false
      }
      throw error
    } finally {
      relationshipStore.setStreamAbortController(null)
      loadingMoreConnectionIds.value = new Set(
        [...loadingMoreConnectionIds.value].filter((id) => id !== connectionId)
      )
    }
  }

  /**
   * Label agent: When a concept node's text changes, regenerate only edges with
   * empty labels. Skips edges that already have content (user or AI).
   */
  function regenerateForNodeIfNeeded(nodeId: string): void {
    if (!llmResultsStore.selectedModel) return
    const connections = diagramStore.data?.connections ?? []
    const affected = connections.filter(
      (c) => (c.source === nodeId || c.target === nodeId) && isLabelEmptyOrPlaceholder(c.label)
    )
    for (const conn of affected) {
      if (conn.id) {
        generateRelationship(conn.id, conn.source, conn.target)
      }
    }
  }

  function dismissOptionsForConnection(connectionId: string): void {
    relationshipStore.clearConnection(connectionId)
  }

  /** Clear all relationship options (on pane click) */
  function dismissAllOptions(): void {
    relationshipStore.clearAll()
  }

  /** Switch displayed label by number (1–5). Picker stays visible until canvas click. */
  function selectOption(connectionId: string, index: number): boolean {
    const opts = relationshipStore.options[connectionId]
    if (!opts || index < 0 || index >= opts.length) return false
    diagramStore.updateConnectionLabel(connectionId, opts[index])
    diagramStore.pushHistory('AI relationship')
    return true
  }

  /** Go to previous page (- key) */
  function prevPage(connectionId: string): boolean {
    return relationshipStore.prevPage(connectionId)
  }

  /** Go to next page (= key). Fetches more when at end. */
  async function nextPage(connectionId: string): Promise<boolean> {
    if (relationshipStore.nextPage(connectionId)) return true
    const fetched = await fetchNextBatch(connectionId)
    if (fetched) {
      return relationshipStore.nextPage(connectionId)
    }
    return false
  }

  return {
    generateRelationship,
    generatingConnectionIds,
    isLoadingMoreFor,
    isGeneratingFor,
    regenerateForNodeIfNeeded,
    dismissOptionsForConnection,
    dismissAllOptions,
    selectOption,
    prevPage,
    nextPage,
    fetchNextBatch,
  }
}
