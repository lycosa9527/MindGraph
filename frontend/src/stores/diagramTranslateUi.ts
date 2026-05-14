/**
 * UI state for full-diagram translate: collab-style banner + streamed progress counts.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useDiagramTranslateUiStore = defineStore('diagramTranslateUi', () => {
  const bannerVisible = ref(false)
  const appliedCount = ref(0)
  const totalCount = ref(0)

  const progressLabel = computed(() => {
    const t = totalCount.value
    const d = appliedCount.value
    if (t <= 0) {
      return '…'
    }
    return `${d} / ${t}`
  })

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
    openBanner,
    setTotal,
    bumpApplied,
    closeBanner,
  }
})
