/**
 * UI state for full-diagram translate: banner, streamed progress, and temp snapshot.
 * Pending target + specs are canvas-session temp data (cleared on leave).
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { ModelLoadPhase } from '@/stores/llmResults'

export const useDiagramTranslateUiStore = defineStore('diagramTranslateUi', () => {
  const bannerVisible = ref(false)
  const appliedCount = ref(0)
  const totalCount = ref(0)
  const streamAbortController = ref<AbortController | null>(null)
  const streamGeneration = ref(0)
  const inFlight = ref(false)
  const phase = ref<ModelLoadPhase>('idle')
  const pendingTargetLanguage = ref<string | null>(null)
  const pendingSourceSpec = ref<Record<string, unknown> | null>(null)
  const translatedSpec = ref<Record<string, unknown> | null>(null)
  const viewingTranslated = ref(false)
  const hasPendingTranslate = computed(
    () => pendingTargetLanguage.value != null && pendingSourceSpec.value != null
  )

  const progressLabel = computed(() => {
    const t = totalCount.value
    const d = appliedCount.value
    if (t <= 0) {
      return '…'
    }
    return `${d} / ${t}`
  })

  function beginStream(): AbortSignal {
    streamAbortController.value?.abort()
    streamAbortController.value = new AbortController()
    streamGeneration.value += 1
    return streamAbortController.value.signal
  }

  function isCurrentGeneration(generation: number): boolean {
    return streamGeneration.value === generation
  }

  function invalidateInFlight(): void {
    streamGeneration.value += 1
    streamAbortController.value?.abort()
    streamAbortController.value = null
    inFlight.value = false
  }

  function abortTranslate(): void {
    invalidateInFlight()
    closeBanner()
    clearPending()
  }

  function armPending(targetLanguage: string, spec: Record<string, unknown>): void {
    pendingTargetLanguage.value = targetLanguage
    pendingSourceSpec.value = spec
    translatedSpec.value = null
    phase.value = 'idle'
  }

  function clearPending(): void {
    pendingTargetLanguage.value = null
    pendingSourceSpec.value = null
    translatedSpec.value = null
    viewingTranslated.value = false
    phase.value = 'idle'
  }

  function setInFlight(value: boolean): void {
    inFlight.value = value
  }

  function setPhase(value: ModelLoadPhase): void {
    phase.value = value
  }

  function setTranslatedSpec(spec: Record<string, unknown> | null): void {
    translatedSpec.value = spec
  }

  function setViewingTranslated(value: boolean): void {
    viewingTranslated.value = value
  }

  function openBanner(): void {
    appliedCount.value = 0
    totalCount.value = 0
    bannerVisible.value = true
  }

  function setTotal(n: number): void {
    totalCount.value = Math.max(0, n)
  }

  function bumpApplied(): void {
    appliedCount.value += 1
  }

  function closeBanner(): void {
    bannerVisible.value = false
    appliedCount.value = 0
    totalCount.value = 0
  }

  return {
    bannerVisible,
    appliedCount,
    totalCount,
    progressLabel,
    inFlight,
    phase,
    pendingTargetLanguage,
    pendingSourceSpec,
    translatedSpec,
    viewingTranslated,
    hasPendingTranslate,
    streamGeneration,
    beginStream,
    isCurrentGeneration,
    invalidateInFlight,
    abortTranslate,
    armPending,
    clearPending,
    setInFlight,
    setPhase,
    setTranslatedSpec,
    setViewingTranslated,
    openBanner,
    setTotal,
    bumpApplied,
    closeBanner,
  }
})
