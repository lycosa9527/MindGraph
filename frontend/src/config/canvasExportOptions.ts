/**
 * Shared export preferences for the new canvas (mind map v2) export dropdown.
 * Persisted in sessionStorage for the current browser tab session.
 */
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'

export type CanvasExportColorMode = 'color' | 'wireframe'

export type CanvasExportLayout = 'landscape' | 'portrait'

export type CanvasExportAnswerMode = 'include' | 'exclude'

export interface CanvasExportOptions {
  colorMode: CanvasExportColorMode
  layout: CanvasExportLayout
  answerMode: CanvasExportAnswerMode
  /** Worksheet header fields — merged at export time from worksheet text settings. */
  worksheetText?: CanvasWorksheetTextOptions
}

export const DEFAULT_CANVAS_EXPORT_OPTIONS: CanvasExportOptions = {
  colorMode: 'color',
  layout: 'landscape',
  answerMode: 'exclude',
}

const STORAGE_KEY = 'mindgraph.canvas.exportOptions'

function isColorMode(value: unknown): value is CanvasExportColorMode {
  return value === 'color' || value === 'wireframe'
}

function isLayout(value: unknown): value is CanvasExportLayout {
  return value === 'landscape' || value === 'portrait'
}

function isAnswerMode(value: unknown): value is CanvasExportAnswerMode {
  return value === 'include' || value === 'exclude'
}

export function loadCanvasExportOptions(): CanvasExportOptions {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_CANVAS_EXPORT_OPTIONS }
    const parsed = JSON.parse(raw) as Partial<CanvasExportOptions>
    return {
      colorMode: isColorMode(parsed.colorMode)
        ? parsed.colorMode
        : DEFAULT_CANVAS_EXPORT_OPTIONS.colorMode,
      layout: isLayout(parsed.layout) ? parsed.layout : DEFAULT_CANVAS_EXPORT_OPTIONS.layout,
      answerMode: isAnswerMode(parsed.answerMode)
        ? parsed.answerMode
        : DEFAULT_CANVAS_EXPORT_OPTIONS.answerMode,
    }
  } catch {
    return { ...DEFAULT_CANVAS_EXPORT_OPTIONS }
  }
}

export function saveCanvasExportOptions(options: CanvasExportOptions): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(options))
  } catch {
    /* ignore private mode / quota */
  }
}
