/**
 * Thin adapter over useCanvasExportStore for existing call sites.
 */
import { storeToRefs } from 'pinia'

import { useCanvasExportStore } from '@/stores/canvasExport'

export function useCanvasExportOptions() {
  const store = useCanvasExportStore()
  const { exportOptions } = storeToRefs(store)
  return {
    exportOptions,
    resetExportOptions: store.resetExportOptions,
  }
}
