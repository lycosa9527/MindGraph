/**
 * New-canvas blank-template ownership.
 *
 * `?type=<diagram>` without `diagramId` always starts from the default template.
 * Sole load owners:
 * - Route bootstrap (CanvasPage / mobile loader mount + in-place type-query watch)
 * - Explicit helpers (`switchCanvasDiagramType`, `useCanvasReset`, Kitty pairing)
 *
 * The selectedChartType watch only syncs `setDiagramType` — never loads templates.
 */
import type { LocationQuery, LocationQueryValue } from 'vue-router'

import {
  VALID_DIAGRAM_TYPES,
  diagramTypeToChineseMap,
} from '@/composables/canvasPage/diagramTypeMaps'
import type { DiagramType } from '@/types'

/** Same-turn dedupe window so mount/helper/route-watch do not double measure-batch. */
const BLANK_CANVAS_DEDUPE_MS = 100

type BlankCanvasLoadStamp = {
  typeKey: string
  atMs: number
}

let lastBlankCanvasLoad: BlankCanvasLoadStamp | null = null

function firstQueryValue(
  value: LocationQueryValue | LocationQueryValue[] | undefined
): string | undefined {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    const first = value[0]
    return typeof first === 'string' ? first : undefined
  }
  return undefined
}

function nowMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now()
  }
  return Date.now()
}

export function normalizeDiagramTypeKey(
  diagramType: string | null | undefined
): string | null {
  if (!diagramType) return null
  if (diagramType === 'mind_map') return 'mindmap'
  return diagramType
}

/** Resolve a valid diagram type from `query.type` (array-safe). */
export function resolveDiagramTypeFromQuery(query: LocationQuery): DiagramType | null {
  const typeStr = firstQueryValue(query.type)
  if (!typeStr || !VALID_DIAGRAM_TYPES.includes(typeStr as DiagramType)) {
    return null
  }
  return typeStr as DiagramType
}

/** True for blank typed entry: `?type=` present and no library diagram id. */
export function isNewCanvasTypeQuery(query: LocationQuery): boolean {
  if (!resolveDiagramTypeFromQuery(query)) return false
  const hasDiagramId = Boolean(
    firstQueryValue(query.diagramId) ?? firstQueryValue(query.diagram_id)
  )
  return !hasDiagramId
}

export function getDiagramDataType(
  data: { type?: unknown } | null | undefined
): string | null {
  return typeof data?.type === 'string' ? data.type : null
}

/**
 * Priority 3 (URL has no `?type=`): whether mount should replace Pinia with the
 * default template.
 *
 * Pass `data.type` (not session `store.type`): the chart-type watch may already
 * have synced the session type without replacing nodes.
 */
export function shouldPriority3LoadDefaultTemplate(options: {
  hasActiveDiagramId: boolean
  hasDiagramData: boolean
  selectedDiagramType: DiagramType
  dataDiagramType: string | null | undefined
}): boolean {
  if (options.hasActiveDiagramId) {
    return !options.hasDiagramData
  }
  if (!options.hasDiagramData) return true
  return (
    normalizeDiagramTypeKey(options.dataDiagramType) !==
    normalizeDiagramTypeKey(options.selectedDiagramType)
  )
}

export type LoadBlankCanvasForTypeOptions = {
  diagramType: DiagramType
  setDiagramType: (diagramType: DiagramType) => boolean
  clearActiveDiagram: () => void
  loadDefaultTemplate: (diagramType: DiagramType) => boolean
  /** Sync UI chrome Chinese key when provided. */
  setSelectedChartType?: (chineseName: string) => void
  /**
   * When true, always load even if the same type was blank-loaded moments ago
   * (canvas reset to default template).
   */
  force?: boolean
  /**
   * When false, never dedupe — session is empty (after leave/`reset`) so a blank
   * must always run. Omit/true allows same-turn switch+route-watch dedupe.
   */
  hasDiagramData?: boolean
}

/**
 * Clear library binding and load the default template for a diagram type.
 * Dedupes same-type blanks within {@link BLANK_CANVAS_DEDUPE_MS} unless `force`
 * or the session has no diagram data.
 */
export function loadBlankCanvasForType(options: LoadBlankCanvasForTypeOptions): boolean {
  const typeKey = normalizeDiagramTypeKey(options.diagramType)
  if (!typeKey) return false

  const at = nowMs()
  const allowDedupe = options.hasDiagramData !== false
  if (
    !options.force &&
    allowDedupe &&
    lastBlankCanvasLoad &&
    lastBlankCanvasLoad.typeKey === typeKey &&
    at - lastBlankCanvasLoad.atMs < BLANK_CANVAS_DEDUPE_MS
  ) {
    return true
  }

  const chineseName = diagramTypeToChineseMap[options.diagramType]
  if (chineseName && options.setSelectedChartType) {
    options.setSelectedChartType(chineseName)
  }

  if (!options.setDiagramType(options.diagramType)) {
    return false
  }
  options.clearActiveDiagram()
  if (!options.loadDefaultTemplate(options.diagramType)) {
    return false
  }

  lastBlankCanvasLoad = { typeKey, atMs: at }
  return true
}

/** Clear same-turn dedupe (canvas leave / store reset / vitest). */
export function clearBlankCanvasLoadDedupe(): void {
  lastBlankCanvasLoad = null
}

/** @internal vitest */
export function resetBlankCanvasLoadDedupeForTests(): void {
  clearBlankCanvasLoadDedupe()
}
