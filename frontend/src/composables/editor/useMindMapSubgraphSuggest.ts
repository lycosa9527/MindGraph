import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { useLanguage, useNotifications } from '@/composables'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useDiagramStore, useLLMResultsStore, useSavedDiagramsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { authFetch } from '@/utils/api'
import {
  extractFailureFromPayload,
  resolveGenerateGraphErrorMessage,
  shouldNotifyGenerateGraphError,
} from '@/utils/generateGraphErrors'
import {
  extractBranchesFromGeneratedSpec,
  toDirectChildrenOnly,
} from '@/utils/mindMapSubgraphMerge'
import {
  collectMindMapSubgraphContext,
  formatMindMapSubgraphPrompt,
  isMindMapSubgraphExpandable,
} from '@/utils/mindMapSubgraphContext'
import {
  beginMindMapSubgraphDebugRun,
  debugMindMapSubgraphMergeLookup,
  endMindMapSubgraphDebugRun,
  mindMapSubgraphDebug,
  mindMapSubgraphDebugError,
  mindMapSubgraphFailureDump,
  summarizeMindMapNodesForDebug,
  type MindMapSubgraphExtractDebug,
  type MindMapSubgraphRequestDebug,
  type MindMapSubgraphResponseDebug,
} from '@/utils/mindMapSubgraphDebug'
import { resolveDiagramLlmModel } from '@/utils/resolveDiagramLlmModel'

const MAX_SUBGRAPH_CHILDREN = 6

function formatSubgraphErrorMessage(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string
): string {
  const message = resolveGenerateGraphErrorMessage(
    rawError,
    errorType,
    t,
    'canvas.subgraphPreview.generationFailed'
  )
  if (message === t('canvas.subgraphPreview.generationFailed')) {
    return message
  }
  return `${t('canvas.subgraphPreview.generationFailed')}：${message}`
}

function notifySubgraphError(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string,
  notify: ReturnType<typeof useNotifications>
): void {
  if (!shouldNotifyGenerateGraphError(rawError, errorType)) {
    return
  }
  notify.error(formatSubgraphErrorMessage(rawError, errorType, t))
}

function buildResponseDebug(
  httpStatus: number,
  result: Record<string, unknown>
): MindMapSubgraphResponseDebug {
  const spec = (result.spec ?? {}) as Record<string, unknown>
  const rawChildren = Array.isArray(spec.children) ? spec.children : []
  const rawSpecChildTexts = rawChildren
    .map((child) => {
      if (!child || typeof child !== 'object') return ''
      const rec = child as Record<string, unknown>
      return String(rec.text ?? rec.label ?? '').trim()
    })
    .filter(Boolean)
  return {
    httpStatus,
    success: result.success as boolean | undefined,
    diagramType: result.diagram_type as string | undefined,
    specKeys: Object.keys(spec),
    specTopic: typeof spec.topic === 'string' ? spec.topic : undefined,
    rawSpecChildrenCount: rawChildren.length,
    rawSpecChildTexts,
    rawResult: result,
  }
}

export function useMindMapSubgraphSuggest() {
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const authStore = useAuthStore()
  const previewStore = useMindMapSubgraphPreviewStore()
  const llmResultsStore = useLLMResultsStore()
  const { isGenerating } = storeToRefs(previewStore)
  const notify = useNotifications()
  const { promptLanguage, t } = useLanguage()

  const isMindMap = computed(
    () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
  )

  async function generateSubgraph(nodeId: string | null): Promise<boolean> {
    beginMindMapSubgraphDebugRun(nodeId ?? '(null)')

    if (!nodeId || !isMindMap.value) {
      mindMapSubgraphDebug('guard', 'aborted: missing nodeId or not a mind map', {
        nodeId,
        diagramType: diagramStore.type,
      })
      endMindMapSubgraphDebugRun(false)
      return false
    }
    if (previewStore.isGenerating) {
      mindMapSubgraphDebug('guard', 'aborted: generation already in flight')
      endMindMapSubgraphDebugRun(false)
      return false
    }
    if (!isMindMapSubgraphExpandable(nodeId)) {
      mindMapSubgraphDebug('guard', 'aborted: node not expandable', { nodeId })
      endMindMapSubgraphDebugRun(false)
      return false
    }

    if (!authStore.isAuthenticated) {
      mindMapSubgraphDebug('guard', 'aborted: not authenticated')
      notify.warning(t('notification.signInToUse'))
      endMindMapSubgraphDebugRun(false)
      return false
    }
    if (diagramStore.collabSessionActive) {
      mindMapSubgraphDebug('guard', 'aborted: collab session active')
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      endMindMapSubgraphDebugRun(false)
      return false
    }

    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    const nodeText = (node?.text ?? '').trim()
    if (!nodeText || isPlaceholderText(nodeText)) {
      mindMapSubgraphDebug('guard', 'aborted: empty or placeholder anchor text', {
        nodeId,
        nodeText,
      })
      notify.warning(t('canvas.subgraphPreview.enterNodeTextFirst'))
      endMindMapSubgraphDebugRun(false)
      return false
    }

    const data = diagramStore.data
    if (!data?.nodes || !data?.connections) {
      mindMapSubgraphDebug('guard', 'aborted: diagram has no nodes/connections')
      endMindMapSubgraphDebugRun(false)
      return false
    }

    mindMapSubgraphDebug('context', 'diagram before request', {
      anchor: { nodeId, nodeText },
      diagram: summarizeMindMapNodesForDebug(data.nodes, data.connections),
      mergeLookup: debugMindMapSubgraphMergeLookup(data.nodes, data.connections, nodeId),
    })

    const subgraphContext = collectMindMapSubgraphContext(data.nodes, data.connections, nodeId)
    if (!subgraphContext) {
      mindMapSubgraphDebug('guard', 'aborted: could not build subgraph context', { nodeId })
      notify.warning(t('canvas.subgraphPreview.enterNodeTextFirst'))
      endMindMapSubgraphDebugRun(false)
      return false
    }

    mindMapSubgraphDebug('context', 'subgraph context', subgraphContext)

    previewStore.beginGeneration(nodeId)
    const nodesBeforeCount = data.nodes.length

    try {
      const diagramId = savedDiagramsStore.activeDiagramId
      const llmModel = resolveDiagramLlmModel(llmResultsStore.selectedModel)
      const signal = previewStore.generationSignal()
      const subgraphPrompt = formatMindMapSubgraphPrompt(subgraphContext, promptLanguage.value)

      const requestBody: Record<string, unknown> = {
        prompt: subgraphPrompt,
        diagram_type: 'mindmap',
        language: promptLanguage.value,
        request_type: 'autocomplete',
        llm: llmModel,
        mind_map_topic: subgraphContext.topic || undefined,
        expand_branch: subgraphContext.expandBranch,
        reference_branches:
          subgraphContext.referenceBranches.length > 0
            ? subgraphContext.referenceBranches
            : undefined,
        existing_branch_children:
          subgraphContext.existingChildren.length > 0
            ? subgraphContext.existingChildren
            : undefined,
        parent_branch: subgraphContext.parentBranch,
        ...(diagramId ? { diagram_id: diagramId } : {}),
      }

      const requestDebug: MindMapSubgraphRequestDebug = {
        endpoint: '/api/generate_graph',
        llm: llmModel,
        language: promptLanguage.value,
        diagramId,
        prompt: subgraphPrompt,
        body: requestBody,
        context: subgraphContext,
      }
      mindMapSubgraphDebug('request', `POST /api/generate_graph → llm=${llmModel}`, requestDebug)

      const response = await authFetch('/api/generate_graph', {
        method: 'POST',
        signal,
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        if (signal?.aborted) {
          mindMapSubgraphDebug('error', 'request aborted')
          previewStore.finishGeneration()
          endMindMapSubgraphDebugRun(false)
          return false
        }
        const errorData = await response.json().catch(() => ({ detail: 'Request failed' }))
        const failure = extractFailureFromPayload(errorData)
        mindMapSubgraphFailureDump({
          stage: 'http_error',
          httpStatus: response.status,
          nodeId,
          llm: llmModel,
          prompt: subgraphPrompt,
          errorData,
          failure,
        })
        if (failure) {
          notifySubgraphError(failure.error, failure.errorType, t, notify)
        } else {
          notifySubgraphError(`HTTP ${response.status}`, undefined, t, notify)
        }
        previewStore.finishGeneration()
        endMindMapSubgraphDebugRun(false)
        return false
      }

      const result = (await response.json()) as Record<string, unknown>
      const responseDebug = buildResponseDebug(response.status, result)
      mindMapSubgraphDebug('response', 'API JSON response', responseDebug)

      if (signal?.aborted) {
        mindMapSubgraphDebug('error', 'aborted after response received')
        previewStore.finishGeneration()
        endMindMapSubgraphDebugRun(false)
        return false
      }
      const payloadFailure = extractFailureFromPayload(result)
      if (payloadFailure) {
        mindMapSubgraphFailureDump({
          stage: 'payload_failure',
          nodeId,
          llm: llmModel,
          prompt: subgraphPrompt,
          response: responseDebug,
          failure: payloadFailure,
        })
        notifySubgraphError(payloadFailure.error, payloadFailure.errorType, t, notify)
        previewStore.finishGeneration()
        endMindMapSubgraphDebugRun(false)
        return false
      }

      const rawExtracted = extractBranchesFromGeneratedSpec(result.spec as Record<string, unknown>)
      const generatedBranches = toDirectChildrenOnly(rawExtracted).slice(0, MAX_SUBGRAPH_CHILDREN)
      const extractDebug: MindMapSubgraphExtractDebug = {
        extractedCount: rawExtracted.length,
        extractedTexts: rawExtracted.map((b) => b.text),
        afterDirectChildrenOnly: generatedBranches,
      }
      mindMapSubgraphDebug('extract', 'branches extracted from spec', extractDebug)

      if (generatedBranches.length === 0) {
        mindMapSubgraphFailureDump({
          stage: 'empty_extract',
          nodeId,
          llm: llmModel,
          prompt: subgraphPrompt,
          response: responseDebug,
          extract: extractDebug,
        })
        notify.warning(t('canvas.subgraphPreview.emptyResult'))
        previewStore.finishGeneration()
        endMindMapSubgraphDebugRun(false)
        return false
      }

      const expanded = diagramStore.expandMindMapPathToNode(nodeId)
      mindMapSubgraphDebug('paste', 'expandMindMapPathToNode', { nodeId, expanded })

      const mergeLookupBeforePaste = debugMindMapSubgraphMergeLookup(
        diagramStore.data?.nodes ?? [],
        diagramStore.data?.connections ?? [],
        nodeId
      )
      mindMapSubgraphDebug('merge', 'lookup immediately before paste', mergeLookupBeforePaste)

      const applied = diagramStore.pasteMindMapClipboardBranches(
        nodeId,
        generatedBranches,
        t('canvas.subgraphPreview.historyLabel')
      )
      const nodesAfterCount = diagramStore.data?.nodes?.length ?? 0

      mindMapSubgraphDebug('paste', 'pasteMindMapClipboardBranches result', {
        anchorNodeId: nodeId,
        applied,
        nodesBeforeCount,
        nodesAfterCount,
        nodesAdded: nodesAfterCount - nodesBeforeCount,
        diagramAfter: diagramStore.data?.nodes
          ? summarizeMindMapNodesForDebug(
              diagramStore.data.nodes,
              diagramStore.data.connections ?? []
            )
          : null,
      })

      previewStore.finishGeneration()
      if (!applied) {
        mindMapSubgraphFailureDump({
          stage: 'merge_failed',
          nodeId,
          llm: llmModel,
          prompt: subgraphPrompt,
          response: responseDebug,
          extract: extractDebug,
          mergeLookup: mergeLookupBeforePaste,
          generatedBranches,
        })
        notify.error(t('canvas.subgraphPreview.mergeFailed'))
        endMindMapSubgraphDebugRun(false)
        return false
      }

      diagramStore.expandMindMapPathToNode(nodeId)
      notify.success(
        `${t('canvas.subgraphPreview.historyLabel')}：${generatedBranches.map((b) => b.text).join('、')}`
      )
      mindMapSubgraphDebug('done', 'subgraph applied successfully', {
        nodeId,
        childCount: generatedBranches.length,
        childTexts: generatedBranches.map((b) => b.text),
      })
      endMindMapSubgraphDebugRun(true)
      return true
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        mindMapSubgraphDebug('error', 'fetch aborted', { name: error.name })
        previewStore.finishGeneration()
        endMindMapSubgraphDebugRun(false)
        return false
      }
      const message =
        error instanceof Error ? error.message : t('canvas.subgraphPreview.generationFailed')
      mindMapSubgraphDebugError('unexpected exception', {
        message,
        error,
        nodeId,
      })
      mindMapSubgraphFailureDump({
        stage: 'exception',
        nodeId,
        message,
        error: error instanceof Error ? { name: error.name, stack: error.stack } : error,
      })
      notify.error(message)
      previewStore.finishGeneration()
      endMindMapSubgraphDebugRun(false)
      return false
    }
  }

  return {
    isGenerating,
    generateSubgraph,
  }
}
