import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { useLanguage, useNotifications } from '@/composables'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useDiagramStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import {
  useMindMapSubgraphPreviewStore,
  type MindMapSubgraphSnapshot,
} from '@/stores/mindMapSubgraphPreview'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { authFetch } from '@/utils/api'
import {
  buildMindMapSpecFromDiagram,
  extractBranchesFromGeneratedSpec,
  mergeGeneratedBranchesIntoSpec,
} from '@/utils/mindMapSubgraphMerge'

const SUBGRAPH_LLM = 'qwen'

function extractApiError(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg?: string }).msg) : ''))
      .filter(Boolean)
      .join('; ')
  }
  return undefined
}

export function useMindMapSubgraphSuggest() {
  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()
  const previewStore = useMindMapSubgraphPreviewStore()
  const { isGenerating, hasPreview, anchorNodeId } = storeToRefs(previewStore)
  const notify = useNotifications()
  const { promptLanguage, t } = useLanguage()

  const isMindMap = computed(
    () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
  )

  function snapshotCurrentState(): MindMapSubgraphSnapshot | null {
    const data = diagramStore.data
    if (!data?.nodes || !data?.connections) return null
    return {
      nodes: structuredClone(data.nodes),
      connections: structuredClone(data.connections),
      nodeStyles: data._node_styles ? structuredClone(data._node_styles) : undefined,
      collapsedPaths: data._collapsed_paths ? [...data._collapsed_paths] : undefined,
    }
  }

  async function generateSubgraph(nodeId: string | null): Promise<void> {
    if (!nodeId || !isMindMap.value) return
    if (previewStore.isGenerating) return

    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return
    }
    if (diagramStore.collabSessionActive) {
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      return
    }

    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    const nodeText = (node?.text ?? '').trim()
    if (!nodeText || isPlaceholderText(nodeText)) {
      notify.warning(t('canvas.subgraphPreview.enterNodeTextFirst'))
      return
    }

    if (previewStore.hasPreview) {
      discardPreview()
    }

    previewStore.beginGeneration(nodeId)

    try {
      const response = await authFetch('/api/generate_graph', {
        method: 'POST',
        body: JSON.stringify({
          prompt: nodeText,
          diagram_type: 'mindmap',
          language: promptLanguage.value,
          request_type: 'autocomplete',
          llm: SUBGRAPH_LLM,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Request failed' }))
        const message = extractApiError(errorData.detail) || `HTTP ${response.status}`
        notify.error(`${t('canvas.subgraphPreview.generationFailed')}：${message}`)
        previewStore.finishGenerationWithoutPreview()
        return
      }

      const result = await response.json()
      const specPayload = result.spec as { success?: boolean; error?: string } | undefined
      const specLooksLikeError =
        specPayload &&
        typeof specPayload === 'object' &&
        specPayload.success === false &&
        typeof specPayload.error === 'string'

      if (!result.success || !result.spec || specLooksLikeError) {
        const nestedError = specLooksLikeError ? specPayload?.error : result.error
        notify.error(
          nestedError
            ? `${t('canvas.subgraphPreview.generationFailed')}：${nestedError}`
            : t('canvas.subgraphPreview.generationFailed')
        )
        previewStore.finishGenerationWithoutPreview()
        return
      }

      const generatedBranches = extractBranchesFromGeneratedSpec(result.spec as Record<string, unknown>)
      if (generatedBranches.length === 0) {
        notify.warning(t('canvas.subgraphPreview.emptyResult'))
        previewStore.finishGenerationWithoutPreview()
        return
      }

      const data = diagramStore.data
      if (!data?.nodes || !data?.connections) {
        previewStore.finishGenerationWithoutPreview()
        return
      }

      const beforeSnapshot = snapshotCurrentState()
      if (!beforeSnapshot) {
        previewStore.finishGenerationWithoutPreview()
        return
      }

      diagramStore.expandMindMapPathToNode(nodeId)

      const oldIds = new Set(data.nodes.map((n) => n.id))
      const currentSpec = buildMindMapSpecFromDiagram(
        diagramStore.data!.nodes,
        diagramStore.data!.connections
      )
      const mergedSpec = mergeGeneratedBranchesIntoSpec(currentSpec, nodeId, generatedBranches)
      if (!mergedSpec) {
        diagramStore.restoreMindMapSubgraphSnapshot(beforeSnapshot)
        notify.error(t('canvas.subgraphPreview.mergeFailed'))
        previewStore.finishGenerationWithoutPreview()
        return
      }

      const reloadResult = loadMindMapSpec({
        topic: mergedSpec.topic,
        leftBranches: mergedSpec.leftBranches,
        rightBranches: mergedSpec.rightBranches,
        preserveLeftRight: true,
      })

      const newNodeIds = reloadResult.nodes.filter((n) => !oldIds.has(n.id)).map((n) => n.id)
      if (newNodeIds.length === 0) {
        diagramStore.restoreMindMapSubgraphSnapshot(beforeSnapshot)
        notify.warning(t('canvas.subgraphPreview.emptyResult'))
        previewStore.finishGenerationWithoutPreview()
        return
      }

      for (const id of newNodeIds) {
        const n = reloadResult.nodes.find((node) => node.id === id)
        if (n) {
          n.data = { ...(n.data ?? {}), subgraphPreview: true }
        }
      }

      diagramStore.applyMindMapSubgraphPreview(reloadResult)
      previewStore.setPreview(nodeId, newNodeIds, beforeSnapshot)
      notify.info(t('canvas.subgraphPreview.previewReady'))
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        previewStore.finishGenerationWithoutPreview()
        return
      }
      const message = error instanceof Error ? error.message : t('canvas.subgraphPreview.generationFailed')
      notify.error(message)
      previewStore.finishGenerationWithoutPreview()
    }
  }

  function acceptPreview(): void {
    if (!previewStore.hasPreview) return
    diagramStore.clearMindMapSubgraphPreviewTags()
    diagramStore.pushHistory(t('canvas.subgraphPreview.historyLabel'))
    previewStore.clear()
    notify.success(t('canvas.subgraphPreview.accepted'))
  }

  function discardPreview(): void {
    if (!previewStore.snapshot) {
      previewStore.clear()
      return
    }
    diagramStore.restoreMindMapSubgraphSnapshot(previewStore.snapshot)
    previewStore.clear()
    notify.info(t('canvas.subgraphPreview.discarded'))
  }

  return {
    isGenerating,
    hasPreview,
    anchorNodeId,
    generateSubgraph,
    acceptPreview,
    discardPreview,
  }
}
