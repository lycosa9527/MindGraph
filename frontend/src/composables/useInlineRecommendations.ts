/**
 * useInlineRecommendations - AI-generated node recommendations for diagram auto-completion
 *
 * Trigger: User fixes topic, double-clicks node to edit, then presses Tab.
 * Streams recommendations via SSE. Similar to useConceptMapRelationship.
 */
import { eventBus } from '@/composables/useEventBus'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useLanguage } from '@/composables/useLanguage'
import { useNotifications } from '@/composables/useNotifications'
import { useDiagramStore, useInlineRecommendationsStore } from '@/stores'

const getInlineRecStore = () => useInlineRecommendationsStore()
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'

import {
  INLINE_RECOMMENDATIONS_NEXT,
  INLINE_RECOMMENDATIONS_START,
  INLINE_RECOMMENDATIONS_SUPPORTED_TYPES,
} from './nodePalette/constants'
import {
  buildStageDataForParent,
  getDefaultStage,
  getStage2ParentsForDiagram,
} from './nodePalette/stageHelpers'

function getStageForNode(
  nodeId: string,
  diagramType: string,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  connections?: Array<{ source: string; target: string }>
): { stage: string; stageData: Record<string, unknown> } {
  const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
  const node = nodes.find((n) => n.id === nodeId)
  if (!node) return { stage: 'branches', stageData: {} }

  const nid = node.id ?? ''
  const parents = getStage2ParentsForDiagram(dt as DiagramType | null, nodes, connections)
  const defaultStage = getDefaultStage(dt as DiagramType | null, nodes, connections)

  if (dt === 'mindmap') {
    if (nid.startsWith('branch-l-1-') || nid.startsWith('branch-r-1-')) {
      const hasChildren = connections?.some((c) => c.source === nid)
      return hasChildren
        ? {
            stage: 'children',
            stageData: buildStageDataForParent({ id: nid, name: (node.text ?? '').trim() }, dt, {}),
          }
        : { stage: 'branches', stageData: {} }
    }
    const parentConn = connections?.find((c) => c.target === nid)
    const parent = parentConn ? parents.find((p) => p.id === parentConn.source) : null
    return parent
      ? {
          stage: 'children',
          stageData: buildStageDataForParent(parent, dt, {}),
        }
      : { stage: defaultStage, stageData: {} }
  }

  if (dt === 'flow_map') {
    if (nid.startsWith('flow-step-')) {
      const hasSubsteps = connections?.some((c) => c.source === nid)
      return hasSubsteps
        ? {
            stage: 'substeps',
            stageData: buildStageDataForParent({ id: nid, name: (node.text ?? '').trim() }, dt, {}),
          }
        : { stage: 'steps', stageData: {} }
    }
    const parentConn = connections?.find((c) => c.target === nid)
    const parent = parentConn ? parents.find((p) => p.id === parentConn.source) : null
    return parent
      ? {
          stage: 'substeps',
          stageData: buildStageDataForParent(parent, dt, {}),
        }
      : { stage: defaultStage, stageData: {} }
  }

  if (dt === 'tree_map') {
    if (nid === 'dimension-label') {
      return { stage: 'dimensions', stageData: {} }
    }
    if (/^tree-cat-\d+$/.test(nid)) {
      const hasChildren = connections?.some((c) => c.source === nid)
      return hasChildren
        ? {
            stage: 'children',
            stageData: buildStageDataForParent({ id: nid, name: (node.text ?? '').trim() }, dt, {}),
          }
        : { stage: 'categories', stageData: {} }
    }
    const parentConn = connections?.find((c) => c.target === nid)
    const parent = parentConn ? parents.find((p) => p.id === parentConn.source) : null
    return parent
      ? {
          stage: 'children',
          stageData: buildStageDataForParent(parent, dt, {}),
        }
      : { stage: defaultStage, stageData: {} }
  }

  if (dt === 'brace_map') {
    if (nid === 'dimension-label') {
      return { stage: 'dimensions', stageData: {} }
    }
    const rootId = nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id
    const isPart =
      node.type === 'brace' &&
      rootId &&
      connections?.some((c) => c.source === rootId && c.target === nid)
    if (isPart) {
      const hasSubparts = connections?.some((c) => c.source === nid)
      return hasSubparts
        ? {
            stage: 'subparts',
            stageData: buildStageDataForParent({ id: nid, name: (node.text ?? '').trim() }, dt, {
              dimension: nodes.find((n) => n.id === 'dimension-label')?.text,
            }),
          }
        : { stage: 'parts', stageData: {} }
    }
    const parentConn = connections?.find((c) => c.target === nid)
    const parent = parentConn ? parents.find((p) => p.id === parentConn.source) : null
    return parent
      ? {
          stage: 'subparts',
          stageData: buildStageDataForParent(parent, dt, {
            dimension: nodes.find((n) => n.id === 'dimension-label')?.text,
          }),
        }
      : { stage: defaultStage, stageData: {} }
  }

  if (dt === 'circle_map') {
    return { stage: 'observations', stageData: {} }
  }

  if (dt === 'bubble_map') {
    return { stage: 'attributes', stageData: {} }
  }

  if (dt === 'double_bubble_map') {
    if (nid.startsWith('similarity-')) {
      return { stage: 'similarities', stageData: {} }
    }
    if (nid.startsWith('left-diff-') || nid.startsWith('right-diff-')) {
      return { stage: 'differences', stageData: {} }
    }
    return { stage: 'similarities', stageData: {} }
  }

  if (dt === 'multi_flow_map') {
    if (nid.startsWith('effect-')) {
      return { stage: 'effects', stageData: {} }
    }
    return { stage: 'causes', stageData: {} }
  }

  if (dt === 'bridge_map') {
    if (nid === 'dimension-label') {
      return { stage: 'dimensions', stageData: {} }
    }
    if (nid.startsWith('pair-') && (nid.endsWith('-left') || nid.endsWith('-right'))) {
      return { stage: 'pairs', stageData: {} }
    }
    return { stage: 'pairs', stageData: {} }
  }

  return { stage: defaultStage, stageData: {} }
}

async function streamRecommendations(
  url: string,
  payload: Record<string, unknown>,
  onText: (text: string) => void,
  onError?: (msg: string) => void,
  signal?: AbortSignal
): Promise<number> {
  const inlineStore = getInlineRecStore()
  inlineStore.setStreamPhase('requesting')
  let count = 0
  try {
    const response = await authFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
    if (!response.ok) {
      onError?.(`Request failed: ${response.status}`)
      return 0
    }
    const reader = response.body?.getReader()
    if (!reader) {
      onError?.('No response body')
      return 0
    }
    const decoder = new TextDecoder()
    let buffer = ''
    let firstReco = false
    try {
      while (true) {
        if (signal?.aborted) break
        const chunk = await reader.read()
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
              text?: string
              message?: string
              source_llm?: string
            }
            if (data.event === 'recommendation_generated' && data.text) {
              if (!firstReco) {
                firstReco = true
                inlineStore.setStreamPhase('streaming')
              }
              count++
              console.log(
                `[InlineRec] #${count} from backend:`,
                data.text,
                data.source_llm ? `(from ${data.source_llm})` : ''
              )
              onText(data.text)
            } else if (data.event === 'error' && data.message) {
              onError?.(data.message)
            } else if (data.event) {
              console.debug('[InlineRec] Event:', data.event, data)
            }
          } catch {
            // Skip malformed
          }
        }
      }
    } finally {
      reader.releaseLock()
      console.log(`[InlineRec] Stream complete: ${count} recommendations received from backend`)
    }
    return count
  } finally {
    inlineStore.setStreamPhase('idle')
  }
}

export function useInlineRecommendations() {
  const diagramStore = useDiagramStore()
  const store = useInlineRecommendationsStore()
  const { t, promptLanguage } = useLanguage()
  const notify = useNotifications()

  function isGeneratingFor(nodeId: string): boolean {
    return store.generatingNodeIds.has(nodeId)
  }

  function optionsFor(nodeId: string): string[] {
    return store.options[nodeId] ?? []
  }

  function selectOption(nodeId: string, index: number): boolean {
    const opts = store.allOptions[nodeId] ?? []
    const globalIdx = store.getGlobalIndex(nodeId, index)
    if (globalIdx < 0 || globalIdx >= opts.length) return false
    const text = opts[globalIdx]
    const dt = diagramStore.type === 'mind_map' ? 'mindmap' : diagramStore.type

    if (dt === 'double_bubble_map' && text.includes('|')) {
      const [leftPart, rightPart] = text.split('|').map((s) => s.trim())
      const leftMatch = nodeId.match(/^left-diff-(\d+)$/)
      const rightMatch = nodeId.match(/^right-diff-(\d+)$/)
      const idx = leftMatch?.[1] ?? rightMatch?.[1]
      if (idx !== undefined && leftPart && rightPart) {
        diagramStore.updateNode(`left-diff-${idx}`, { text: leftPart })
        diagramStore.updateNode(`right-diff-${idx}`, { text: rightPart })
        diagramStore.pushHistory('AI recommendation')
        eventBus.emit('inline_recommendation:applied', {
          nodeId: `left-diff-${idx}`,
          text: leftPart,
        })
        eventBus.emit('inline_recommendation:applied', {
          nodeId: `right-diff-${idx}`,
          text: rightPart,
        })
        eventBus.emit('node:text_updated', { nodeId: `left-diff-${idx}`, text: leftPart })
        eventBus.emit('node:text_updated', { nodeId: `right-diff-${idx}`, text: rightPart })
        return true
      }
    }

    if (dt === 'bridge_map' && text.includes('|')) {
      const [leftPart, rightPart] = text.split('|').map((s) => s.trim())
      const leftMatch = nodeId.match(/^pair-(\d+)-left$/)
      const rightMatch = nodeId.match(/^pair-(\d+)-right$/)
      const idx = leftMatch?.[1] ?? rightMatch?.[1]
      if (idx !== undefined && leftPart && rightPart) {
        diagramStore.updateNode(`pair-${idx}-left`, { text: leftPart })
        diagramStore.updateNode(`pair-${idx}-right`, { text: rightPart })
        diagramStore.pushHistory('AI recommendation')
        eventBus.emit('inline_recommendation:applied', {
          nodeId: `pair-${idx}-left`,
          text: leftPart,
        })
        eventBus.emit('inline_recommendation:applied', {
          nodeId: `pair-${idx}-right`,
          text: rightPart,
        })
        eventBus.emit('node:text_updated', { nodeId: `pair-${idx}-left`, text: leftPart })
        eventBus.emit('node:text_updated', { nodeId: `pair-${idx}-right`, text: rightPart })
        return true
      }
    }

    diagramStore.updateNode(nodeId, { text })
    diagramStore.pushHistory('AI recommendation')
    eventBus.emit('inline_recommendation:applied', { nodeId, text })
    eventBus.emit('node:text_updated', { nodeId, text })
    return true
  }

  async function startRecommendations(nodeId: string): Promise<{
    success: boolean
    error?: string
  }> {
    if (store.generatingNodeIds.has(nodeId)) {
      return { success: false, error: 'Already generating' }
    }

    const dt = diagramStore.type
    const normalizedDt = dt === 'mind_map' ? 'mindmap' : dt
    if (
      !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(normalizedDt ?? '')
    ) {
      return { success: false, error: 'Diagram type not supported' }
    }

    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    const { stage } = getStageForNode(nodeId, normalizedDt ?? '', nodes, connections)

    store.setGenerating(nodeId, true)
    store.setActive(nodeId)

    const diagramData = diagramStore.data as Record<string, unknown> | undefined
    const educationalContext = diagramData?.educational_context as
      | Record<string, unknown>
      | undefined

    const payload = {
      session_id: nodeId,
      diagram_type: normalizedDt,
      stage,
      node_id: nodeId,
      nodes: nodes.map((n) => ({
        id: n.id,
        text: n.text ?? (n.data as { label?: string })?.label ?? '',
        type: n.type,
      })),
      connections: connections.map((c) => ({
        source: c.source,
        target: c.target,
      })),
      language: promptLanguage.value,
      count: 10,
      ...(educationalContext && { educational_context: educationalContext }),
    }

    const controller = new AbortController()
    store.setStreamAbortController(controller)

    console.log('[InlineRec] Starting stream for node:', nodeId, '| stage:', stage)
    const labels: string[] = []
    const onText = (text: string) => {
      labels.push(text)
      store.setOptions(nodeId, [...labels], labels.length > 1)
      const totalInStore = store.allOptions[nodeId]?.length ?? 0
      console.log(`[InlineRec] Store now has ${totalInStore} for ${nodeId} (latest: "${text}")`)
    }
    const onError = (msg: string) => {
      notify.error(t('notification.recommendationFailed', { msg }))
    }

    try {
      await ensureFontsForLanguageCode(promptLanguage.value)
      const count = await streamRecommendations(
        INLINE_RECOMMENDATIONS_START,
        payload,
        onText,
        onError,
        controller.signal
      )

      const nodeStillExists = diagramStore.data?.nodes?.some((n) => n.id === nodeId)
      if (!nodeStillExists) {
        return { success: false, error: 'Node deleted' }
      }

      if (count > 0) {
        const finalInStore = store.allOptions[nodeId]?.length ?? 0
        console.log(
          `[InlineRec] Done. Backend sent ${count}, store has ${finalInStore} for ${nodeId}`
        )
        return { success: true }
      }
      return { success: false, error: 'No recommendations generated' }
    } catch (error) {
      const isAbort = error instanceof Error && error.name === 'AbortError'
      if (isAbort) {
        const had = store.allOptions[nodeId]?.length ?? 0
        console.warn(`[InlineRec] Stream ABORTED for ${nodeId}. Had ${had} in store before abort.`)
        return { success: false, error: 'Aborted' }
      }
      const errMsg = error instanceof Error ? error.message : 'Unknown error'
      notify.error(t('notification.recommendationFailed', { msg: errMsg }))
      return { success: false, error: errMsg }
    } finally {
      store.setStreamAbortController(null)
      store.setGenerating(nodeId, false)
    }
  }

  async function fetchNextBatch(nodeId: string): Promise<boolean> {
    if (store.generatingNodeIds.has(nodeId)) return false
    if (store.fetchingNextBatchNodeIds.has(nodeId)) return false

    store.setFetchingNextBatch(nodeId, true)
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    const dt = diagramStore.type
    const normalizedDt = dt === 'mind_map' ? 'mindmap' : dt
    const { stage } = getStageForNode(nodeId, normalizedDt ?? '', nodes, connections)

    const diagramData = diagramStore.data as Record<string, unknown> | undefined
    const educationalContext = diagramData?.educational_context as
      | Record<string, unknown>
      | undefined

    const payload = {
      session_id: nodeId,
      diagram_type: normalizedDt,
      stage,
      node_id: nodeId,
      nodes: nodes.map((n) => ({
        id: n.id,
        text: n.text ?? (n.data as { label?: string })?.label ?? '',
        type: n.type,
      })),
      connections: connections.map((c) => ({
        source: c.source,
        target: c.target,
      })),
      language: promptLanguage.value,
      count: 10,
      ...(educationalContext && { educational_context: educationalContext }),
    }

    const controller = new AbortController()
    store.setStreamAbortController(controller)
    const newOpts: string[] = []
    try {
      await ensureFontsForLanguageCode(promptLanguage.value)
      await streamRecommendations(
        INLINE_RECOMMENDATIONS_NEXT,
        payload,
        (t) => newOpts.push(t),
        (msg) => notify.error(msg),
        controller.signal
      )
      if (newOpts.length > 0) {
        store.appendOptions(nodeId, newOpts)
      }
      return newOpts.length > 0
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return false
      throw error
    } finally {
      store.setFetchingNextBatch(nodeId, false)
      store.setStreamAbortController(null)
    }
  }

  function isLoadingMoreFor(nodeId: string): boolean {
    return store.fetchingNextBatchNodeIds.has(nodeId)
  }

  function prevPage(nodeId: string): boolean {
    return store.prevPage(nodeId)
  }

  async function nextPage(nodeId: string): Promise<boolean> {
    if (store.nextPage(nodeId)) return true
    const fetched = await fetchNextBatch(nodeId)
    if (fetched) return store.nextPage(nodeId)
    return false
  }

  function dismissOptions(nodeId: string): void {
    store.invalidateForNode(nodeId)
  }

  function dismissAll(): void {
    store.invalidateAll()
  }

  return {
    startRecommendations,
    selectOption,
    prevPage,
    nextPage,
    fetchNextBatch,
    dismissOptions,
    dismissAll,
    isGeneratingFor,
    isLoadingMoreFor,
    optionsFor,
    getStageForNode,
  }
}
