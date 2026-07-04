import { nextTick } from 'vue'

import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

type ExportVisualStore = {
  setExportWireframeOutline: (active: boolean) => void
  setExportRasterCapture: (active: boolean) => void
}

const EXPORT_INSTANT_CLASS = 'wireframe-mode--export-instant'
const EXPORT_OUTLINE_CLASS = 'export-outline-wireframe'
const EXPORT_RASTER_CLASS = 'export-raster-capture'

export function isWireframeExport(options: CanvasExportOptions | undefined): boolean {
  return options?.colorMode === 'wireframe'
}

export async function runWithExportVisualMode<T>(
  uiStore: ExportVisualStore,
  container: HTMLElement | null,
  options: CanvasExportOptions | undefined,
  run: () => T | Promise<T>
): Promise<T> {
  const exportWireframe = isWireframeExport(options)
  uiStore.setExportWireframeOutline(exportWireframe)
  uiStore.setExportRasterCapture(true)

  if (container) {
    container.classList.add(EXPORT_INSTANT_CLASS)
    container.classList.add(EXPORT_RASTER_CLASS)
    if (exportWireframe) {
      container.classList.add(EXPORT_OUTLINE_CLASS)
    }
  }

  try {
    await nextTick()
    await waitForNextPaint()
    await waitForNextPaint()
    return await run()
  } finally {
    if (container) {
      container.classList.remove(EXPORT_INSTANT_CLASS)
      container.classList.remove(EXPORT_RASTER_CLASS)
      container.classList.remove(EXPORT_OUTLINE_CLASS)
    }
    uiStore.setExportWireframeOutline(false)
    uiStore.setExportRasterCapture(false)
  }
}
