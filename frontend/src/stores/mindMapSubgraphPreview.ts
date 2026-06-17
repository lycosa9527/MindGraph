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

  const hasPreview = computed(() => active.value && previewNodeIds.value.length > 0)

  function beginGeneration(nodeId: string) {
    isGenerating.value = true
    anchorNodeId.value = nodeId
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
  }

  function clear() {
    active.value = false
    anchorNodeId.value = null
    previewNodeIds.value = []
    snapshot.value = null
    isGenerating.value = false
  }

  function finishGenerationWithoutPreview() {
    isGenerating.value = false
  }

  return {
    active,
    anchorNodeId,
    previewNodeIds,
    isGenerating,
    snapshot,
    hasPreview,
    beginGeneration,
    setPreview,
    clear,
    finishGenerationWithoutPreview,
  }
})
