/**
 * Insert / delete / child / remap ops for mind-map v2 summaries.
 */
import { i18n } from '@/i18n'
import type {
  Connection,
  DiagramData,
  DiagramNode,
  MindMapSummaryChromePatch,
  MindMapSummarySpec,
} from '@/types'
import {
  areConsecutiveSiblingPaths,
  insertSummaryChildAt,
  isMindMapSummaryNodeId,
  mindMapSummaryRootNodeId,
  parseMindMapSummaryNodeId,
  readMindMapSummaries,
  remapMindMapSummariesAfterReload,
  resolveConsecutiveSiblingRange,
  sameMindMapSummaryPaths,
  updateSummaryChildText,
  writeMindMapSummaries,
} from '@/utils/mindMapSummary'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

import { remapMindMapNodeIdAfterReload } from './mindMapCollapse'
import { rematerializeMindMapSummaryNodes } from './mindMapSummaryLayout'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

function defaultChildText(): string {
  return String(i18n.global.t('diagram.newChild'))
}

function rematerialize(ctx: DiagramContext): void {
  if (!ctx.data.value) return
  rematerializeMindMapSummaryNodes(
    ctx.data.value,
    ctx.mindMapNodeWidths.value,
    ctx.mindMapNodeHeights.value
  )
}

export function insertMindMapSummaryFromSelection(
  ctx: DiagramContext,
  defaultText: string
): boolean {
  if (isDiagramPresentationReadOnly(ctx)) return false
  const data = ctx.data.value
  if (!data?.nodes || !data.connections) return false
  const range = resolveConsecutiveSiblingRange(
    ctx.selectedNodes.value,
    data.nodes,
    data.connections
  )
  if (!range.ok) return false

  ctx.pushHistory(String(i18n.global.t('canvas.ribbon.summary')))
  const summaries = readMindMapSummaries(data)
  const next: MindMapSummarySpec = {
    id: safeRandomUUID(),
    text: defaultText,
    coveredPaths: range.coveredPaths,
  }
  writeMindMapSummaries(data, [...summaries, next])
  rematerialize(ctx)
  ctx.selectedNodes.value = [mindMapSummaryRootNodeId(next.id)]
  ctx.scheduleMindMapRecalc()
  return true
}

export function deleteMindMapSummariesByNodeIds(
  ctx: DiagramContext,
  nodeIds: readonly string[],
  options?: { skipHistory?: boolean }
): number {
  if (isDiagramPresentationReadOnly(ctx)) return 0
  const data = ctx.data.value
  if (!data) return 0
  const parsed = nodeIds
    .map((id) => parseMindMapSummaryNodeId(id))
    .filter((item): item is NonNullable<typeof item> => item != null)
  if (parsed.length === 0) return 0

  const dropIds = new Set(parsed.map((item) => item.summaryId))
  const summaries = readMindMapSummaries(data)
  const next = summaries.filter((item) => !dropIds.has(item.id))
  if (next.length === summaries.length) return 0

  if (!options?.skipHistory) {
    ctx.pushHistory(String(i18n.global.t('canvas.ribbon.summaryDelete')))
  }
  writeMindMapSummaries(data, next)
  rematerialize(ctx)
  ctx.selectedNodes.value = ctx.selectedNodes.value.filter((id) => !isMindMapSummaryNodeId(id))
  ctx.scheduleMindMapRecalc()
  return summaries.length - next.length
}

export function addMindMapSummaryChild(
  ctx: DiagramContext,
  summaryNodeId: string,
  placement: 'child' | 'above' | 'below' = 'child'
): boolean {
  if (isDiagramPresentationReadOnly(ctx)) return false
  const data = ctx.data.value
  if (!data) return false
  const parsed = parseMindMapSummaryNodeId(summaryNodeId)
  if (!parsed) return false

  const summaries = readMindMapSummaries(data)
  const index = summaries.findIndex((item) => item.id === parsed.summaryId)
  if (index < 0) return false

  ctx.pushHistory(String(i18n.global.t('diagram.newChild')))
  const target = summaries[index]
  const text = defaultChildText()
  let children = target.children
  if (placement === 'child') {
    children = insertSummaryChildAt(children, parsed.childPath, text, 'end')
  } else {
    children = insertSummaryChildAt(children, parsed.childPath, text, placement)
  }
  const next = [...summaries]
  next[index] = { ...target, children }
  writeMindMapSummaries(data, next)
  rematerialize(ctx)
  ctx.scheduleMindMapRecalc()
  return true
}

export function syncMindMapSummaryNodeText(data: DiagramData, nodeId: string, text: string): void {
  const parsed = parseMindMapSummaryNodeId(nodeId)
  if (!parsed) return
  const summaries = readMindMapSummaries(data)
  const index = summaries.findIndex((item) => item.id === parsed.summaryId)
  if (index < 0) return
  const target = summaries[index]
  if (parsed.childPath.length === 0) {
    if (target.text === text) return
    const next = [...summaries]
    next[index] = { ...target, text }
    writeMindMapSummaries(data, next)
    return
  }
  const children = updateSummaryChildText(target.children, parsed.childPath, text)
  const next = [...summaries]
  next[index] = { ...target, children }
  writeMindMapSummaries(data, next)
}

export function remapAndRematerializeMindMapSummaries(
  data: DiagramData,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  widths: Record<string, number>,
  heights: Record<string, number>
): void {
  const remapped = remapMindMapSummariesAfterReload(
    readMindMapSummaries(data),
    oldNodes,
    oldConnections,
    newNodes,
    newConnections,
    remapMindMapNodeIdAfterReload
  )
  writeMindMapSummaries(data, remapped)
  rematerializeMindMapSummaryNodes(data, widths, heights)
}

export function updateMindMapSummaryCoveredPaths(
  ctx: DiagramContext,
  summaryId: string,
  coveredPaths: readonly string[]
): boolean {
  if (isDiagramPresentationReadOnly(ctx)) return false
  const data = ctx.data.value
  if (!data) return false
  const paths = [...coveredPaths]
  if (paths.length === 0 || !areConsecutiveSiblingPaths(paths)) return false
  const summaries = readMindMapSummaries(data)
  const index = summaries.findIndex((item) => item.id === summaryId)
  if (index < 0) return false
  const target = summaries[index]
  if (sameMindMapSummaryPaths(target.coveredPaths, paths)) return false

  ctx.pushHistory(String(i18n.global.t('canvas.ribbon.summary')))
  const next = [...summaries]
  next[index] = { ...target, coveredPaths: paths }
  writeMindMapSummaries(data, next)
  rematerialize(ctx)
  ctx.scheduleMindMapRecalc()
  return true
}

export function updateMindMapSummaryChrome(
  ctx: DiagramContext,
  summaryId: string,
  patch: MindMapSummaryChromePatch
): boolean {
  if (isDiagramPresentationReadOnly(ctx)) return false
  const data = ctx.data.value
  if (!data) return false
  const summaries = readMindMapSummaries(data)
  const index = summaries.findIndex((item) => item.id === summaryId)
  if (index < 0) return false

  const target = summaries[index]
  const nextItem: MindMapSummarySpec = { ...target, ...patch }
  if (
    nextItem.kind === target.kind &&
    nextItem.lineStyle === target.lineStyle &&
    nextItem.strokeColor === target.strokeColor &&
    nextItem.strokeWidth === target.strokeWidth
  ) {
    return false
  }

  ctx.pushHistory(String(i18n.global.t('canvas.floatingToolbar.summaryStyle')))
  const next = [...summaries]
  next[index] = nextItem
  writeMindMapSummaries(data, next)
  if (nextItem.kind !== target.kind) {
    rematerialize(ctx)
    ctx.scheduleMindMapRecalc()
  }
  return true
}

export function summaryInsertFailureReason(
  nodeIds: readonly string[],
  nodes: readonly DiagramNode[],
  connections: readonly Connection[]
): ReturnType<typeof resolveConsecutiveSiblingRange> {
  return resolveConsecutiveSiblingRange(nodeIds, nodes, connections)
}
