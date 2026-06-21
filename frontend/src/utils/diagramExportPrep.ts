/**
 * Shared prep for diagram raster export (PNG/SVG/PDF thumbnails, community share).
 */
import { nextTick } from 'vue'

import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'

import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

export async function waitForDiagramExportFonts(promptLanguage: string): Promise<void> {
  await ensureFontsForLanguageCode(promptLanguage)
  if (typeof document !== 'undefined' && document.fonts?.ready) {
    await document.fonts.ready
  }
}

/** Fit diagram to export framing, then wait for layout/paint (optional fit callback). */
export async function prepareDiagramCanvasForRasterCapture(fitForExport?: () => void): Promise<void> {
  if (fitForExport) {
    fitForExport()
  }
  await nextTick()
  await waitForNextPaint()
}
