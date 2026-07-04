import { ref, watch } from 'vue'

import {
  DEFAULT_CANVAS_EXPORT_OPTIONS,
  loadCanvasExportOptions,
  saveCanvasExportOptions,
  type CanvasExportOptions,
} from '@/config/canvasExportOptions'

const exportOptions = ref<CanvasExportOptions>(loadCanvasExportOptions())

watch(
  exportOptions,
  (value) => {
    saveCanvasExportOptions(value)
  },
  { deep: true }
)

export function useCanvasExportOptions() {
  function resetExportOptions(): void {
    exportOptions.value = { ...DEFAULT_CANVAS_EXPORT_OPTIONS }
  }

  return {
    exportOptions,
    resetExportOptions,
  }
}
