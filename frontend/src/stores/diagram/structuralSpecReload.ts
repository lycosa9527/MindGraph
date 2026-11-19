import { FORMAT_BRUSH_KEYS } from '@/composables/canvasToolbar/formatBrushStyle'
import type { Connection, DiagramNode, NodeStyle } from '@/types'

import { LEARNING_SHEET_BLANK_TEXT, isLearningSheetBlankDisplayText } from '../specLoader/utils'

const STRUCTURAL_SESSION_KEYS = [
  '_node_styles',
  '_customPositions',
  '_mindmap_theme',
  '_mindmap_adornments',
  'isLearningSheet',
  'is_learning_sheet',
  'learningSheetShowAnswers',
  'learning_sheet_show_answers',
  'hiddenAnswers',
  'learningSheetBaseline',
  'learning_sheet_baseline',
] as const

export function structuralSessionCarry(
  data: Record<string, unknown> | undefined
): Record<string, unknown> | undefined {
  if (!data) return undefined
  const carried: Record<string, unknown> = {}
  for (const key of STRUCTURAL_SESSION_KEYS) {
    if (data[key] !== undefined) carried[key] = data[key]
  }
  return Object.keys(carried).length > 0 ? carried : undefined
}

function hiddenAnswerFields(node: DiagramNode | undefined): Record<string, unknown> | undefined {
  const data = node?.data
  if (!data) return undefined
  const answer = typeof data.hiddenAnswer === 'string' ? data.hiddenAnswer : ''
  const secondary = typeof data.hiddenAnswerSecondary === 'string' ? data.hiddenAnswerSecondary : ''
  if (!answer && !secondary) return undefined
  return {
    ...(answer ? { hiddenAnswer: answer } : {}),
    ...(secondary ? { hiddenAnswerSecondary: secondary } : {}),
  }
}

function wasBlanked(node: DiagramNode): boolean {
  const data = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
  const answer = typeof data?.hiddenAnswer === 'string' ? data.hiddenAnswer.trim() : ''
  if (!answer) return false
  return data?.hidden === true || isLearningSheetBlankDisplayText(node.text)
}

function carriedHold(node: DiagramNode): Record<string, number> {
  const data = node.data as
    { learningSheetHoldWidth?: unknown; learningSheetHoldHeight?: unknown } | undefined
  const hold: Record<string, number> = {}
  if (typeof data?.learningSheetHoldWidth === 'number' && data.learningSheetHoldWidth > 0) {
    hold.learningSheetHoldWidth = data.learningSheetHoldWidth
  }
  if (typeof data?.learningSheetHoldHeight === 'number' && data.learningSheetHoldHeight > 0) {
    hold.learningSheetHoldHeight = data.learningSheetHoldHeight
  }
  return hold
}

/** Text that decides a node's painted size; equal signatures can reuse a measured box. */
export function nodeLabelSignature(node: DiagramNode): string {
  return `${node.text ?? ''}\u0001${node.textSecondary ?? ''}`
}

/**
 * Loader stamps layout sizes; keep hand-painted format keys from the previous node.
 * Double-bubble rebuilds re-stamp rainbow fill/border on diffs — without this, format
 * brush / style edits vanish after typography or add/delete relayout.
 * Do not re-spread previous layout sizes (`width` / `minWidth` / …) — flow row stretch
 * would otherwise stick on `data.nodes` after a structural reload.
 */
export function mergeReloadedNodeStyle(
  previous: NodeStyle | undefined,
  next: NodeStyle | undefined
): NodeStyle | undefined {
  if (!previous && !next) return undefined
  if (!previous) return next ? { ...next } : undefined
  const formatFromPrevious: NodeStyle = {}
  for (const key of FORMAT_BRUSH_KEYS) {
    const value = previous[key]
    if (value !== undefined) {
      ;(formatFromPrevious as Record<string, unknown>)[key] = value
    }
  }
  if (!next) {
    return Object.keys(formatFromPrevious).length > 0 ? formatFromPrevious : undefined
  }
  return { ...next, ...formatFromPrevious }
}

function connectionStyleKey(connection: Connection): string {
  if (connection.id) return `id:${connection.id}`
  return `ends:${connection.source}\u0001${connection.target}`
}

/** Keep connector stroke (and other edge style) when structure reloads recreate edges. */
export function mergeReloadedConnections(
  connections: Connection[],
  previous: Connection[] | undefined
): Connection[] {
  if (!previous || previous.length === 0) return connections
  const prevByKey = new Map(previous.map((conn) => [connectionStyleKey(conn), conn] as const))
  return connections.map((conn) => {
    const prev = prevByKey.get(connectionStyleKey(conn))
    if (!prev?.style) return conn
    return {
      ...conn,
      style: { ...conn.style, ...prev.style },
    }
  })
}

/** Keep typography and worksheet answers on nodes whose ids survive a structure reload. */
export function mergeReloadedNodeFields(
  nodes: DiagramNode[],
  previous: DiagramNode[] | undefined,
  structural: boolean
): DiagramNode[] {
  if (!previous || previous.length === 0) return nodes
  const prevById = new Map(previous.map((node) => [node.id, node] as const))
  return nodes.map((node) => {
    const prev = prevById.get(node.id)
    if (!prev) return node
    const answers = structural ? hiddenAnswerFields(prev) : undefined
    const mergedStyle = mergeReloadedNodeStyle(prev.style, node.style)
    if (structural && wasBlanked(prev)) {
      return {
        ...node,
        text: LEARNING_SHEET_BLANK_TEXT,
        textSecondary: '',
        ...(mergedStyle ? { style: mergedStyle } : {}),
        data: {
          ...(node.data ?? {}),
          ...(answers ?? {}),
          ...carriedHold(prev),
          hidden: true,
          label: LEARNING_SHEET_BLANK_TEXT,
          labelSecondary: '',
        },
      }
    }
    if (!mergedStyle && !answers) return node
    return {
      ...node,
      ...(mergedStyle ? { style: mergedStyle } : {}),
      ...(answers ? { data: { ...(node.data ?? {}), ...answers } } : {}),
    }
  })
}
