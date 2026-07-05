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
}

export const DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS: CanvasWorksheetTextOptions = {
  showTopic: false,
  showName: false,
  showClass: false,
  showDate: false,
  showInstruction: false,
  instructionText: '',
}

/** Classroom-friendly preset applied from the modal reset action. */
export const CLASSROOM_WORKSHEET_TEXT_PRESET: CanvasWorksheetTextOptions = {
  showTopic: true,
  showName: true,
  showClass: true,
  showDate: true,
  showInstruction: true,
  instructionText: '',
}

const STORAGE_KEY = 'mindgraph.canvas.worksheetText'

function readBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
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
