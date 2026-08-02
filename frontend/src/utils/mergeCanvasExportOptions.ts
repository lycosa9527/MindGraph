/**
 * Merge toolbar/modal export options.
 * Worksheet headers are opt-in: only attached when the caller (or an explicit
 * fallback) provides worksheetText — plain PDF export stays header-free.
 */
import {
  DEFAULT_CANVAS_EXPORT_OPTIONS,
  type CanvasExportOptions,
} from '@/config/canvasExportOptions'
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'

export function mergeCanvasExportOptions(
  options: CanvasExportOptions | undefined,
  worksheetTextFallback?: CanvasWorksheetTextOptions
): CanvasExportOptions {
  const worksheetText = options?.worksheetText
    ? { ...options.worksheetText }
    : worksheetTextFallback
      ? { ...worksheetTextFallback }
      : undefined

  return {
    ...DEFAULT_CANVAS_EXPORT_OPTIONS,
    ...options,
    worksheetText,
  }
}
