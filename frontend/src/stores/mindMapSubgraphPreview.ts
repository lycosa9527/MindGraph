import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { Connection, DiagramNode, NodeStyle } from '@/types'

export interface MindMapSubgraphSnapshot {
  nodes: DiagramNode[]
  connections: Connection[]
  nodeStyles?: Record<string, NodeStyle>
  collapsedPaths?: string[]
}

export const useMindMapSubgraphPreviewStore = defineStore('mindMapSubgraphPreview', () => {
  const active = ref(false)
  const anchorNodeId = ref<string | null>(null)
  const previewNodeIds = ref<string[]>([])
  const isGenerating = ref(false)
  const snapshot = ref<MindMapSubgraphSnapshot | null>(null)
  const streamAbortController = ref<AbortController | null>(null)

  const hasPreview = computed(() => active.value && previewNodeIds.value.length > 0)

  function abortGeneration(): void {
    if (streamAbortController.value) {
      streamAbortController.value.abort()
      streamAbortController.value = null
    }
    isGenerating.value = false
  }

  function beginGeneration(nodeId: string) {
    abortGeneration()
    streamAbortController.value = new AbortController()
    isGenerating.value = true
    anchorNodeId.value = nodeId
  }

  function generationSignal(): AbortSignal | undefined {
    return streamAbortController.value?.signal
  }

  function setPreview(
    nodeId: string,
    nodeIds: string[],
    stateSnapshot: MindMapSubgraphSnapshot
  ) {
    active.value = true
    anchorNodeId.value = nodeId
    previewNodeIds.value = nodeIds
    snapshot.value = stateSnapshot
    isGenerating.value = false
    streamAbortController.value = null
  }

  function clear() {
    abortGeneration()
    active.value = false
    anchorNodeId.value = null
    previewNodeIds.value = []
    snapshot.value = null
  }

  function finishGenerationWithoutPreview() {
    isGenerating.value = false
    streamAbortController.value = null
  }

  return {
    active,
    anchorNodeId,
    previewNodeIds,
    isGenerating,
    snapshot,
    hasPreview,
    beginGeneration,
    generationSignal,
    setPreview,
    clear,
    finishGenerationWithoutPreview,
  }
})
