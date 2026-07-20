import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { safeRandomUUID } from '@/utils/safeRandomUUID'

type SubgraphJob = {
  nodeId: string
  controller: AbortController
}

/** Tracks in-flight mind-map AI subgraph generation (multi-branch safe). */
export const useMindMapSubgraphPreviewStore = defineStore('mindMapSubgraphPreview', () => {
  /** Stable job key → job (survives path-id remap on mind-map reload). */
  const jobs = new Map<string, SubgraphJob>()
  const generatingNodeIds = ref<Set<string>>(new Set())

  const isGenerating = computed(() => generatingNodeIds.value.size > 0)

  /** First generating id (compat for single-glow call sites). */
  const generatingNodeId = computed<string | null>(() => {
    const ids = generatingNodeIds.value
    if (ids.size === 0) return null
    return ids.values().next().value ?? null
  })

  function syncGeneratingNodeIds(): void {
    const next = new Set<string>()
    for (const job of jobs.values()) {
      next.add(job.nodeId)
    }
    generatingNodeIds.value = next
  }

  function isGeneratingFor(nodeId: string): boolean {
    return generatingNodeIds.value.has(nodeId)
  }

  function beginGeneration(nodeId: string): { signal: AbortSignal; jobKey: string } {
    // Replace an in-flight job for the same anchor (double-click / retry).
    for (const [key, job] of [...jobs.entries()]) {
      if (job.nodeId === nodeId) {
        job.controller.abort()
        jobs.delete(key)
      }
    }
    const jobKey = safeRandomUUID()
    const controller = new AbortController()
    jobs.set(jobKey, { nodeId, controller })
    syncGeneratingNodeIds()
    return { signal: controller.signal, jobKey }
  }

  function generationSignal(jobKey: string): AbortSignal | undefined {
    return jobs.get(jobKey)?.controller.signal
  }

  /** Finish one job by stable key (preferred after id remaps). */
  function finishJob(jobKey: string): void {
    if (!jobs.has(jobKey)) {
      return
    }
    jobs.delete(jobKey)
    syncGeneratingNodeIds()
  }

  /**
   * Compat: finish jobs for a node id, or abort all when omitted.
   * Prefer ``finishJob`` when a jobKey is available.
   */
  function finishGeneration(nodeId?: string | null): void {
    if (!nodeId) {
      abortGeneration()
      return
    }
    for (const [key, job] of [...jobs.entries()]) {
      if (job.nodeId === nodeId) {
        jobs.delete(key)
      }
    }
    syncGeneratingNodeIds()
  }

  function abortGeneration(): void {
    for (const job of jobs.values()) {
      job.controller.abort()
    }
    jobs.clear()
    generatingNodeIds.value = new Set()
  }

  function remapGeneratingNodeIds(remap: (id: string) => string | null): void {
    if (jobs.size === 0) return
    for (const job of jobs.values()) {
      job.nodeId = remap(job.nodeId) || job.nodeId
    }
    syncGeneratingNodeIds()
  }

  function clear(): void {
    abortGeneration()
  }

  return {
    isGenerating,
    generatingNodeId,
    generatingNodeIds,
    isGeneratingFor,
    beginGeneration,
    generationSignal,
    finishJob,
    finishGeneration,
    abortGeneration,
    remapGeneratingNodeIds,
    clear,
  }
})
