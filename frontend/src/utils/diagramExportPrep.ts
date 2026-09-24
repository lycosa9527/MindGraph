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

/**
 * Load export fonts, fit the painted diagram, then wait for layout/paint.
 * Fonts must settle before fit: a late font swap grows nodes after the frame
 * and the viewport clips the new size.
 */
export async function prepareDiagramCanvasForRasterCapture(
  fitForExport?: () => void | Promise<unknown>,
  options?: { promptLanguage?: string }
): Promise<void> {
  if (options?.promptLanguage) {
    await waitForDiagramExportFonts(options.promptLanguage)
    await nextTick()
    await waitForNextPaint()
  }
  if (fitForExport) {
    await fitForExport()
  }
  await nextTick()
  await waitForNextPaint()
}
