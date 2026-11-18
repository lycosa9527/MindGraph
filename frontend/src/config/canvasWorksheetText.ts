/**
 * Worksheet header fields for classroom print/export (name, class, date, instructions).
 * Persisted in sessionStorage for the current browser tab session.
 */
import {
  type WorksheetCompareArrangement,
  normalizeWorksheetCompareArrangement,
} from '@/utils/worksheetCompareLayout'
import {
  type WorksheetDiagramCrop,
  normalizeWorksheetDiagramCrop,
} from '@/utils/worksheetDiagramCrop'

export type WorksheetMode = 'single' | 'compare'

export type { WorksheetCompareArrangement }

export type WorksheetCompareSourceKind = 'current' | 'model' | 'snapshot'

export type WorksheetCompareSlot = {
  kind: WorksheetCompareSourceKind
  /** Model id or snapshot version number as string. */
  id?: string
}

/** Runtime raster pair for compare export (not persisted). */
export type WorksheetCompareRaster = {
  dataUrl: string
  width: number
  height: number
  label: string
  blob: Blob
}

export type WorksheetComparePair = {
  left: WorksheetCompareRaster
  right: WorksheetCompareRaster
}

export interface CanvasWorksheetTextOptions {
  /** When false, export is a plain DOC/PDF with no classroom header. */
  learningSheetMode: boolean
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
  /**
   * Fraction of the source image hidden on each edge (0 = none).
   * The remaining window is what PDF / Word export draws.
   */
  diagramCropTop: number
  diagramCropRight: number
  diagramCropBottom: number
  diagramCropLeft: number
  /** Single diagram (default) or side-by-side compare. */
  worksheetMode: WorksheetMode
  /** Left|right vs top/bottom packing for compare mode. */
  compareLayout: WorksheetCompareArrangement
  compareLeft: WorksheetCompareSlot
  compareRight: WorksheetCompareSlot
  /** Right/bottom panel placement (left/top reuses diagramOffset*). */
  compareRightOffsetX: number
  compareRightOffsetY: number
  compareRightScale: number
  compareRightCropTop: number
  compareRightCropRight: number
  compareRightCropBottom: number
  compareRightCropLeft: number
}

export const DEFAULT_COMPARE_SLOT: WorksheetCompareSlot = { kind: 'current' }

export const DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS: CanvasWorksheetTextOptions = {
  learningSheetMode: false,
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
  diagramCropTop: 0,
  diagramCropRight: 0,
  diagramCropBottom: 0,
  diagramCropLeft: 0,
  worksheetMode: 'single',
  compareLayout: 'horizontal',
  compareLeft: { ...DEFAULT_COMPARE_SLOT },
  compareRight: { ...DEFAULT_COMPARE_SLOT },
  compareRightOffsetX: 0,
  compareRightOffsetY: 0,
  compareRightScale: 1,
  compareRightCropTop: 0,
  compareRightCropRight: 0,
  compareRightCropBottom: 0,
  compareRightCropLeft: 0,
}

/** Classroom-friendly preset applied from the modal reset action. */
export const CLASSROOM_WORKSHEET_TEXT_PRESET: CanvasWorksheetTextOptions = {
  ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  learningSheetMode: true,
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

function readCropEdge(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

export function normalizeWorksheetCompareSlot(value: unknown): WorksheetCompareSlot {
  if (!value || typeof value !== 'object') return { ...DEFAULT_COMPARE_SLOT }
  const raw = value as { kind?: unknown; id?: unknown }
  const kind = raw.kind
  if (kind === 'model' || kind === 'snapshot') {
    const id = typeof raw.id === 'string' && raw.id.trim() ? raw.id.trim() : undefined
    if (!id) return { ...DEFAULT_COMPARE_SLOT }
    return { kind, id }
  }
  return { ...DEFAULT_COMPARE_SLOT }
}

export function normalizeWorksheetMode(value: unknown): WorksheetMode {
  return value === 'compare' ? 'compare' : 'single'
}

export function isWorksheetCompareMode(options: CanvasWorksheetTextOptions | undefined): boolean {
  return options?.worksheetMode === 'compare'
}

export function worksheetCompareSlotKey(slot: WorksheetCompareSlot): string {
  if (slot.kind === 'current') return 'current'
  return `${slot.kind}:${slot.id ?? ''}`
}

export function parseWorksheetCompareSlotKey(key: string): WorksheetCompareSlot {
  if (key === 'current' || !key) return { ...DEFAULT_COMPARE_SLOT }
  const sep = key.indexOf(':')
  if (sep <= 0) return { ...DEFAULT_COMPARE_SLOT }
  const kind = key.slice(0, sep)
  const id = key.slice(sep + 1).trim()
  if ((kind === 'model' || kind === 'snapshot') && id) {
    return { kind, id }
  }
  return { ...DEFAULT_COMPARE_SLOT }
}

export function worksheetDiagramCropFromOptions(
  options: CanvasWorksheetTextOptions | undefined
): WorksheetDiagramCrop {
  return normalizeWorksheetDiagramCrop({
    top: options?.diagramCropTop ?? 0,
    right: options?.diagramCropRight ?? 0,
    bottom: options?.diagramCropBottom ?? 0,
    left: options?.diagramCropLeft ?? 0,
  })
}

export function hasActiveWorksheetHeader(options: CanvasWorksheetTextOptions | undefined): boolean {
  if (!options?.learningSheetMode) return false
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
    const crop = normalizeWorksheetDiagramCrop({
      top: readCropEdge(parsed.diagramCropTop),
      right: readCropEdge(parsed.diagramCropRight),
      bottom: readCropEdge(parsed.diagramCropBottom),
      left: readCropEdge(parsed.diagramCropLeft),
    })
    const rightCrop = normalizeWorksheetDiagramCrop({
      top: readCropEdge(parsed.compareRightCropTop),
      right: readCropEdge(parsed.compareRightCropRight),
      bottom: readCropEdge(parsed.compareRightCropBottom),
      left: readCropEdge(parsed.compareRightCropLeft),
    })
    return {
      learningSheetMode: readBoolean(parsed.learningSheetMode, defaults.learningSheetMode),
      showTopic: readBoolean(parsed.showTopic, defaults.showTopic),
      showName: readBoolean(parsed.showName, defaults.showName),
      showClass: readBoolean(parsed.showClass, defaults.showClass),
      showDate: readBoolean(parsed.showDate, defaults.showDate),
      showInstruction: readBoolean(parsed.showInstruction, defaults.showInstruction),
      instructionText:
        typeof parsed.instructionText === 'string'
          ? parsed.instructionText
          : defaults.instructionText,
      topicText: typeof parsed.topicText === 'string' ? parsed.topicText : defaults.topicText,
      diagramOffsetX: readOffset(parsed.diagramOffsetX, defaults.diagramOffsetX),
      diagramOffsetY: readOffset(parsed.diagramOffsetY, defaults.diagramOffsetY),
      diagramScale: readScale(parsed.diagramScale, defaults.diagramScale),
      diagramCropTop: crop.top,
      diagramCropRight: crop.right,
      diagramCropBottom: crop.bottom,
      diagramCropLeft: crop.left,
      worksheetMode: normalizeWorksheetMode(parsed.worksheetMode),
      compareLayout: normalizeWorksheetCompareArrangement(parsed.compareLayout),
      compareLeft: normalizeWorksheetCompareSlot(parsed.compareLeft),
      compareRight: normalizeWorksheetCompareSlot(parsed.compareRight),
      compareRightOffsetX: readOffset(parsed.compareRightOffsetX, defaults.compareRightOffsetX),
      compareRightOffsetY: readOffset(parsed.compareRightOffsetY, defaults.compareRightOffsetY),
      compareRightScale: readScale(parsed.compareRightScale, defaults.compareRightScale),
      compareRightCropTop: rightCrop.top,
      compareRightCropRight: rightCrop.right,
      compareRightCropBottom: rightCrop.bottom,
      compareRightCropLeft: rightCrop.left,
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
