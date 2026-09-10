/**
 * Drop the temp translate preview when leaving the canvas (gallery / back).
 * Restores the original spec first so a later leave-flush cannot persist translation.
 */
import { getActivePinia } from 'pinia'

import { useDiagramStore } from '@/stores/diagram'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useLLMResultsStore } from '@/stores/llmResults'
import type { DiagramType } from '@/types'

function asDiagramType(value: unknown): DiagramType | null {
  if (typeof value !== 'string') {
    return null
  }
  return VALID_DIAGRAM_TYPES.includes(value as DiagramType) ? (value as DiagramType) : null
}

export function discardCanvasTranslatePreview(): void {
  if (!getActivePinia()) {
    return
  }
  const translateUi = useDiagramTranslateUiStore()
  const original = translateUi.pendingSourceSpec
  const wasViewing = translateUi.viewingTranslated
  translateUi.invalidateInFlight()
  if (wasViewing && original) {
    const diagramStore = useDiagramStore()
    const diagramType = asDiagramType(diagramStore.type) ?? asDiagramType(original.type)
    if (diagramType) {
      useLLMResultsStore().contentChangeIsFromModelSwitch = true
      diagramStore.loadFromSpec(original, diagramType, {
        preserveMindMapMeasures: true,
        preferLaidOutMindMapNodes: true,
      })
    }
  }
  translateUi.abortTranslate()
}
