/**
 * Worksheet header fields for classroom print/export (name, class, date, instructions).
 * Persisted in sessionStorage for the current browser tab session.
 */

export interface CanvasWorksheetTextOptions {
  showTopic: boolean
  showName: boolean
  showClass: boolean
  showDate: boolean
  showInstruction: boolean
  /** Empty string uses the locale default instruction. */
  instructionText: string
  /** Empty string falls back to the current diagram title at export time. */
  topicText: string
  /**
   * Diagram placement in the A4 content region below the header.
   * Normalized [-1, 1]; 0 = centered (default PDF fit).
   */
  diagramOffsetX: number
  diagramOffsetY: number
  /** Relative to max-fit size in the content region; clamped to 0.25–1. */
  diagramScale: number
}

export const DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS: CanvasWorksheetTextOptions = {
  showTopic: true,
  showName: true,
  showClass: true,
  showDate: true,
  showInstruction: true,
  instructionText: '',
  topicText: '',
  diagramOffsetX: 0,
  diagramOffsetY: 0,
  diagramScale: 1,
}

/** Classroom-friendly preset applied from the modal reset action. */
export const CLASSROOM_WORKSHEET_TEXT_PRESET: CanvasWorksheetTextOptions = {
  ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
}

/** v2 — defaults flipped to show-all; ignore stale v1 all-hidden session values. */
const STORAGE_KEY = 'mindgraph.canvas.worksheetText.v2'

function readBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function readOffset(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.max(-1, Math.min(1, value))
}

function readScale(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.max(0.25, Math.min(1, value))
}

export function hasActiveWorksheetHeader(options: CanvasWorksheetTextOptions | undefined): boolean {
  if (!options) return false
  return (
    options.showTopic ||
    options.showName ||
    options.showClass ||
    options.showDate ||
    options.showInstruction
  )
}

/** Prefer worksheet topic override; otherwise use the diagram export title. */
export function resolveWorksheetTopicText(
  options: CanvasWorksheetTextOptions | undefined,
  fallbackTitle: string
): string {
  const override = options?.topicText?.trim()
  if (override) return override
  return fallbackTitle.trim()
}

export function loadCanvasWorksheetTextOptions(): CanvasWorksheetTextOptions {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS }
    const parsed = JSON.parse(raw) as Partial<CanvasWorksheetTextOptions>
    const defaults = DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS
    return {
      showTopic: readBoolean(parsed.showTopic, defaults.showTopic),
      showName: readBoolean(parsed.showName, defaults.showName),
      showClass: readBoolean(parsed.showClass, defaults.showClass),
      showDate: readBoolean(parsed.showDate, defaults.showDate),
      showInstruction: readBoolean(parsed.showInstruction, defaults.showInstruction),
      instructionText:
        typeof parsed.instructionText === 'string' ? parsed.instructionText : defaults.instructionText,
      topicText: typeof parsed.topicText === 'string' ? parsed.topicText : defaults.topicText,
      diagramOffsetX: readOffset(parsed.diagramOffsetX, defaults.diagramOffsetX),
      diagramOffsetY: readOffset(parsed.diagramOffsetY, defaults.diagramOffsetY),
      diagramScale: readScale(parsed.diagramScale, defaults.diagramScale),
    }
  } catch {
    return { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS }
  }
}

export function saveCanvasWorksheetTextOptions(options: CanvasWorksheetTextOptions): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(options))
  } catch {
    /* ignore private mode / quota */
  }
}
