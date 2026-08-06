import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { applyKittyTopicSeedToDiagram } from '@/composables/canvasPage/applyKittyTopicSeedToDiagram'
import type { KittyTopicSeed } from '@/composables/canvasPage/diagramTypeFromPrompt'
import { loadBlankCanvasForType } from '@/composables/canvasPage/newCanvasBootstrap'
import { useDiagramStore, useSavedDiagramsStore, useUIStore } from '@/stores'
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
  const savedDiagramsStore = useSavedDiagramsStore()

  applyCanvasSessionReset()

  if (
    !loadBlankCanvasForType({
      diagramType: targetType,
      setDiagramType: (type) => diagramStore.setDiagramType(type),
      clearActiveDiagram: () => savedDiagramsStore.clearActiveDiagram(),
      loadDefaultTemplate: (type) => diagramStore.loadDefaultTemplate(type),
      setSelectedChartType: (name) => uiStore.setSelectedChartType(name),
      // Session still has prior-type data until load replaces it — allow switch↔watch dedupe.
      hasDiagramData: true,
    })
  ) {
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
