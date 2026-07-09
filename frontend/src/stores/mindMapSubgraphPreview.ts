import { ref } from 'vue'

import { defineStore } from 'pinia'

/** Tracks in-flight mind-map AI subgraph generation (loading state + abort). */
export const useMindMapSubgraphPreviewStore = defineStore('mindMapSubgraphPreview', () => {
  const isGenerating = ref(false)
  const generatingNodeId = ref<string | null>(null)
  const streamAbortController = ref<AbortController | null>(null)

  function abortGeneration(): void {
    if (streamAbortController.value) {
      streamAbortController.value.abort()
      streamAbortController.value = null
    }
    isGenerating.value = false
    generatingNodeId.value = null
  }

  function beginGeneration(nodeId: string): void {
    abortGeneration()
    streamAbortController.value = new AbortController()
    generatingNodeId.value = nodeId
    isGenerating.value = true
  }

  function generationSignal(): AbortSignal | undefined {
    return streamAbortController.value?.signal
  }

  function finishGeneration(): void {
    isGenerating.value = false
    streamAbortController.value = null
  }

  function clear(): void {
    abortGeneration()
  }

  return {
    isGenerating,
    generatingNodeId,
    beginGeneration,
    generationSignal,
    finishGeneration,
    clear,
  }
})
