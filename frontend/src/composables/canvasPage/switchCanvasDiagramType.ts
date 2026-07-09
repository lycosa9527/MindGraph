import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { applyKittyTopicSeedToDiagram } from '@/composables/canvasPage/applyKittyTopicSeedToDiagram'
import { diagramTypeToChineseMap } from '@/composables/canvasPage/diagramTypeMaps'
import type { KittyTopicSeed } from '@/composables/canvasPage/diagramTypeFromPrompt'
import { useDiagramStore, useUIStore } from '@/stores'
import type { DiagramType } from '@/types'

export type SwitchCanvasDiagramTypeOptions = {
  topicSeed?: KittyTopicSeed
  router?: Router
  route?: RouteLocationNormalizedLoaded
}

/**
 * Replace the current ephemeral canvas with a new diagram type, preserving topic seed.
 * Keeps Kitty hub scope / one-sentence chat session ids unchanged (caller responsibility).
 */
export function switchCanvasDiagramType(
  targetType: DiagramType,
  options: SwitchCanvasDiagramTypeOptions = {}
): boolean {
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()

  applyCanvasSessionReset()

  const chineseName = diagramTypeToChineseMap[targetType]
  if (chineseName) {
    uiStore.setSelectedChartType(chineseName)
  }

  if (!diagramStore.setDiagramType(targetType)) {
    return false
  }

  if (!diagramStore.loadDefaultTemplate(targetType)) {
    return false
  }

  if (options.topicSeed) {
    applyKittyTopicSeedToDiagram(targetType, options.topicSeed, diagramStore)
  }

  const router = options.router
  const route = options.route
  if (router && route) {
    const nextQuery: Record<string, string> = { type: targetType }
    void router.replace({ path: route.path, query: nextQuery }).catch(() => undefined)
  }

  return true
}
