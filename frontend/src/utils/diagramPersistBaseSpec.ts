/**
 * Library persist must keep the pre-translate snapshot while the canvas shows
 * a translated preview.
 */
import { useDiagramStore } from '@/stores/diagram'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'

import { cloneDiagramSpecJson } from './cloneDiagramSpecJson'

export function getDiagramPersistBaseSpec(): Record<string, unknown> | null {
  const translateUi = useDiagramTranslateUiStore()
  if (translateUi.viewingTranslated && translateUi.pendingSourceSpec) {
    return cloneDiagramSpecJson(translateUi.pendingSourceSpec)
  }
  return useDiagramStore().getSpecForSave()
}

export function shouldStampLiveCanvasOntoLlmResult(): boolean {
  return !useDiagramTranslateUiStore().viewingTranslated
}
