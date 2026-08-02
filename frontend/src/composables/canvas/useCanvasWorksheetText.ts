/**
 * Thin adapter over useCanvasExportStore for existing call sites.
 */
import { storeToRefs } from 'pinia'

import { useCanvasExportStore } from '@/stores/canvasExport'

export function useCanvasWorksheetText() {
  const store = useCanvasExportStore()
  const { worksheetTextOptions } = storeToRefs(store)
  return {
    worksheetTextOptions,
    resetWorksheetTextOptions: store.resetWorksheetTextOptions,
  }
}
