/**
 * On the course-builder route, canvas tab clicks drive the shared ribbon.
 * Course tools stay up until a canvas tab is chosen.
 */
import { type ComputedRef, type Ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

import type { MindMapRibbonTabId } from '@/canvas-ribbon/mindMapRibbonTypes'
import { isTrainingBuilderPath } from '@/utils/trainingClient'

import { builderRibbonToolOwner, claimBuilderCanvasRibbon } from './builderCanvasRibbon'

export function useBuilderCanvasRibbonMerge(ribbon: {
  classic: Ref<boolean>
  selectTab: (tab: MindMapRibbonTabId) => void
  setActiveTab: (tab: MindMapRibbonTabId) => void
  setClassic: (open: boolean) => void
}): {
  inBuilder: ComputedRef<boolean>
  quietCanvasTabs: ComputedRef<boolean>
  onRibbonTab: (tab: MindMapRibbonTabId) => void
} {
  const route = useRoute()
  const inBuilder = computed(() => isTrainingBuilderPath(route.path))
  const quietCanvasTabs = computed(
    () => inBuilder.value && builderRibbonToolOwner.value !== 'canvas'
  )
  let release = (): void => undefined

  function onRibbonTab(tab: MindMapRibbonTabId): void {
    if (inBuilder.value && builderRibbonToolOwner.value !== 'canvas') {
      ribbon.setActiveTab(tab)
      ribbon.setClassic(true)
      builderRibbonToolOwner.value = 'canvas'
      return
    }
    ribbon.selectTab(tab)
    if (inBuilder.value) {
      builderRibbonToolOwner.value = ribbon.classic.value ? 'canvas' : 'course'
    }
  }

  onMounted(() => {
    if (inBuilder.value) release = claimBuilderCanvasRibbon()
  })

  onUnmounted(() => {
    release()
  })

  return { inBuilder, quietCanvasTabs, onRibbonTab }
}
