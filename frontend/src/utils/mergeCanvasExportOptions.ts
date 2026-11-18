/**
 * Merge toolbar/modal export options.
 * Worksheet headers are opt-in: only attached when the caller (or an explicit
 * fallback) provides worksheetText — plain PDF export stays header-free.
 */
import {
  type CanvasExportOptions,
  DEFAULT_CANVAS_EXPORT_OPTIONS,
} from '@/config/canvasExportOptions'
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'

function cloneWorksheetText(
  value: CanvasWorksheetTextOptions | undefined
): CanvasWorksheetTextOptions | undefined {
  if (!value) return undefined
  return {
    ...value,
    compareLeft: { ...value.compareLeft },
    compareRight: { ...value.compareRight },
  }
}

export function mergeCanvasExportOptions(
  options: CanvasExportOptions | undefined,
  worksheetTextFallback?: CanvasWorksheetTextOptions
): CanvasExportOptions {
  const worksheetText =
    cloneWorksheetText(options?.worksheetText) ?? cloneWorksheetText(worksheetTextFallback)

  return {
    ...DEFAULT_CANVAS_EXPORT_OPTIONS,
    ...options,
    worksheetText,
    // Runtime dual rasters — keep explicitly so spreads never drop Blobs/data URLs.
    comparePair: options?.comparePair,
  }
}
