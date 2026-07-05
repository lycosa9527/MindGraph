import { ref, watch } from 'vue'

import {
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  loadCanvasWorksheetTextOptions,
  saveCanvasWorksheetTextOptions,
  type CanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'

const worksheetTextOptions = ref<CanvasWorksheetTextOptions>(loadCanvasWorksheetTextOptions())

watch(
  worksheetTextOptions,
  (value) => {
    saveCanvasWorksheetTextOptions(value)
  },
  { deep: true }
)

export function useCanvasWorksheetText() {
  function resetWorksheetTextOptions(): void {
    worksheetTextOptions.value = { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS }
  }

  return {
    worksheetTextOptions,
    resetWorksheetTextOptions,
  }
}
