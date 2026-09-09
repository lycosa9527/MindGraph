/**
 * Mind-map v2 summary (概要) — ids, extras, consecutive-sibling range.
 */
import type {
  Connection,
  DiagramData,
  DiagramNode,
  MindMapSummaryChildSpec,
  MindMapSummaryKind,
  MindMapSummaryLineStyle,
  MindMapSummarySpec,
} from '@/types'
import { MINDMAP_TOPIC_ID, isMindMapTopicId, mindMapLocationPathKey } from '@/utils/mindMapLocation'

export const MINDMAP_SUMMARY_KINDS = ['brace', 'bracket', 'paren'] as const
export const MINDMAP_SUMMARY_LINE_STYLES = ['solid', 'dashed', 'dotted'] as const
export const MINDMAP_SUMMARY_STROKE_WIDTH_MIN = 1
export const MINDMAP_SUMMARY_STROKE_WIDTH_MAX = 8
export const MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH = 2

const STROKE_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

export function parseMindMapSummaryKind(raw: unknown): MindMapSummaryKind | undefined {
  return MINDMAP_SUMMARY_KINDS.find((kind) => kind === raw)
}

export function parseMindMapSummaryLineStyle(raw: unknown): MindMapSummaryLineStyle | undefined {
  return MINDMAP_SUMMARY_LINE_STYLES.find((style) => style === raw)
}

export function parseMindMapSummaryStrokeColor(raw: unknown): string | undefined {
  if (typeof raw !== 'string') return undefined
  const color = raw.trim()
  return STROKE_COLOR_RE.test(color) ? color : undefined
}

export function parseMindMapSummaryStrokeWidth(raw: unknown): number | undefined {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return undefined
  const width = Math.round(raw)
  if (width < MINDMAP_SUMMARY_STROKE_WIDTH_MIN || width > MINDMAP_SUMMARY_STROKE_WIDTH_MAX) {
    return undefined
  }
  return width
}

export function resolveMindMapSummaryKind(spec: MindMapSummarySpec): MindMapSummaryKind {
  return spec.kind ?? 'brace'
}

export function resolveMindMapSummaryLineStyle(spec: MindMapSummarySpec): MindMapSummaryLineStyle {
  return spec.lineStyle ?? 'solid'
}

export function resolveMindMapSummaryStrokeWidth(spec: MindMapSummarySpec): number {
  return spec.strokeWidth ?? MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH
}

export function mindMapSummaryStrokeDasharray(
  lineStyle: MindMapSummaryLineStyle,
  strokeWidth: number
): string | undefined {
  if (lineStyle === 'dashed') {
    return `${Math.max(4, strokeWidth * 3)} ${Math.max(3, strokeWidth * 2)}`
  }
  if (lineStyle === 'dotted') {
    return `${Math.max(1, strokeWidth)} ${Math.max(2, strokeWidth * 1.8)}`
  }
  return undefined
}

function mindMapNodePathKey(nodeId: string, connections: Connection[]): string | null {
  return mindMapLocationPathKey(nodeId, connections)
}

function findNodeIdByPathKey(
  nodes: DiagramNode[],
  connections: Connection[],
  pathKey: string
): string | null {
  if (pathKey === MINDMAP_TOPIC_ID) {
    return nodes.find((n) => n.id === MINDMAP_TOPIC_ID)?.id ?? null
  }
  for (const node of nodes) {
    if (mindMapNodePathKey(node.id, connections) === pathKey) {
      return node.id
    }
  }
  return null
}

export const MINDMAP_SUMMARY_ID_PREFIX = 'smry:'

export function isMindMapSummaryNodeId(nodeId: string | undefined): boolean {
  return typeof nodeId === 'string' && nodeId.startsWith(MINDMAP_SUMMARY_ID_PREFIX)
}

export function isMindMapSummaryNode(
  node: { type?: string; id?: string } | null | undefined
): boolean {
  if (!node) return false
  return node.type === 'summary' || isMindMapSummaryNodeId(node.id)
}

export function mindMapSummaryRootNodeId(summaryId: string): string {
  return `${MINDMAP_SUMMARY_ID_PREFIX}${summaryId}`
}

export function mindMapSummaryChildNodeId(summaryId: string, indexPath: number[]): string {
  if (indexPath.length === 0) return mindMapSummaryRootNodeId(summaryId)
  return `${MINDMAP_SUMMARY_ID_PREFIX}${summaryId}:${indexPath.join('.')}`
}

export type ParsedSummaryNodeId = {
  summaryId: string
  childPath: number[]
}

export function parseMindMapSummaryNodeId(nodeId: string): ParsedSummaryNodeId | null {
  if (!isMindMapSummaryNodeId(nodeId)) return null
  const rest = nodeId.slice(MINDMAP_SUMMARY_ID_PREFIX.length)
  const colon = rest.indexOf(':')
  if (colon < 0) {
    return rest ? { summaryId: rest, childPath: [] } : null
  }
  const summaryId = rest.slice(0, colon)
  const pathPart = rest.slice(colon + 1)
  if (!summaryId) return null
  if (!pathPart) return { summaryId, childPath: [] }
  const childPath = pathPart.split('.').map((part) => Number.parseInt(part, 10))
  if (childPath.some((n) => !Number.isInteger(n) || n < 0)) return null
  return { summaryId, childPath }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

function parseSummaryChildren(raw: unknown): MindMapSummaryChildSpec[] | undefined {
  if (!Array.isArray(raw)) return undefined
  const children: MindMapSummaryChildSpec[] = []
  for (const item of raw) {
    if (!isPlainObject(item)) continue
    const text = typeof item.text === 'string' ? item.text : ''
    const nested = parseSummaryChildren(item.children)
    children.push(nested ? { text, children: nested } : { text })
  }
  return children.length > 0 ? children : undefined
}

export function parseMindMapSummaries(raw: unknown): MindMapSummarySpec[] {
  if (!Array.isArray(raw)) return []
  const out: MindMapSummarySpec[] = []
  for (const item of raw) {
    if (!isPlainObject(item)) continue
    const id = typeof item.id === 'string' ? item.id.trim() : ''
    if (!id) continue
    const text = typeof item.text === 'string' ? item.text : ''
    const coveredPaths = Array.isArray(item.coveredPaths)
      ? item.coveredPaths.filter((p): p is string => typeof p === 'string' && p.length > 0)
      : []
    if (coveredPaths.length === 0) continue
    const children = parseSummaryChildren(item.children)
    const kind = parseMindMapSummaryKind(item.kind)
    const lineStyle = parseMindMapSummaryLineStyle(item.lineStyle)
    const strokeColor = parseMindMapSummaryStrokeColor(item.strokeColor)
    const strokeWidth = parseMindMapSummaryStrokeWidth(item.strokeWidth)
    const spec: MindMapSummarySpec = { id, text, coveredPaths }
    if (children) spec.children = children
    if (kind) spec.kind = kind
    if (lineStyle) spec.lineStyle = lineStyle
    if (strokeColor) spec.strokeColor = strokeColor
    if (strokeWidth != null) spec.strokeWidth = strokeWidth
    out.push(spec)
  }
  return out
}

export function readMindMapSummaries(
  data: Record<string, unknown> | DiagramData | null | undefined
): MindMapSummarySpec[] {
  if (!data) return []
  return parseMindMapSummaries((data as Record<string, unknown>)._mindmap_summaries)
}

export function writeMindMapSummaries(
  data: Record<string, unknown> | DiagramData,
  summaries: MindMapSummarySpec[]
): void {
  const record = data as Record<string, unknown>
  if (summaries.length === 0) {
    delete record._mindmap_summaries
    return
  }
  record._mindmap_summaries = summaries
}

export type SiblingRangeResult =
  | { ok: true; coveredPaths: string[] }
  | {
      ok: false
      reason: 'need-nodes' | 'topic' | 'not-siblings' | 'not-consecutive' | 'summary'
    }

function pathParentPrefix(pathKey: string): string | null {
  if (pathKey === MINDMAP_TOPIC_ID) return null
  const slash = pathKey.lastIndexOf('/')
  if (slash < 0) return null
  return pathKey.slice(0, slash)
}

function pathLastIndex(pathKey: string): number | null {
  const slash = pathKey.lastIndexOf('/')
  if (slash < 0) return null
  const idx = Number.parseInt(pathKey.slice(slash + 1), 10)
  return Number.isInteger(idx) && idx >= 0 ? idx : null
}

/** True when paths share a parent and last-segment indices are consecutive. */
export function areConsecutiveSiblingPaths(paths: readonly string[]): boolean {
  if (paths.length === 0) return false
  if (paths.some((p) => p === MINDMAP_TOPIC_ID)) return false
  const prefix = pathParentPrefix(paths[0])
  if (prefix == null) return false
  const indices: number[] = []
  for (const path of paths) {
    if (pathParentPrefix(path) !== prefix) return false
    const idx = pathLastIndex(path)
    if (idx == null) return false
    indices.push(idx)
  }
  indices.sort((a, b) => a - b)
  for (let i = 1; i < indices.length; i += 1) {
    if (indices[i] !== indices[i - 1] + 1) return false
  }
  return true
}

export function sortSiblingPaths(paths: readonly string[]): string[] {
  return [...paths].sort((a, b) => {
    const ia = pathLastIndex(a) ?? 0
    const ib = pathLastIndex(b) ?? 0
    return ia - ib
  })
}

export function sameMindMapSummaryPaths(
  left: readonly string[],
  right: readonly string[]
): boolean {
  if (left.length !== right.length) return false
  return left.every((path, index) => path === right[index])
}

/** Every tree path that shares the parent of the current 概要 range. */
export function siblingPathsSharingParent(
  coveredPaths: readonly string[],
  nodes: readonly DiagramNode[],
  connections: readonly Connection[]
): string[] {
  if (coveredPaths.length === 0) return []
  const prefix = pathParentPrefix(coveredPaths[0])
  if (prefix == null) return []
  const paths: string[] = []
  for (const node of nodes) {
    if (isMindMapSummaryNode(node)) continue
    const path = mindMapNodePathKey(node.id, connections as Connection[])
    if (!path || pathParentPrefix(path) !== prefix) continue
    if (!paths.includes(path)) paths.push(path)
  }
  return sortSiblingPaths(paths)
}

export type SummaryVerticalSlot = {
  path: string
  y: number
  height: number
}

/**
 * Consecutive sibling paths whose vertical centers lie in `[topY, bottomY]`.
 * If none match, the closest sibling is kept so the range is never empty.
 */
export function coveredPathsFromVerticalRange(
  slots: readonly SummaryVerticalSlot[],
  topY: number,
  bottomY: number
): string[] {
  if (slots.length === 0) return []
  const lo = Math.min(topY, bottomY)
  const hi = Math.max(topY, bottomY)
  const hitIndexes: number[] = []
  for (let index = 0; index < slots.length; index += 1) {
    const slot = slots[index]
    const mid = slot.y + slot.height / 2
    if (mid >= lo && mid <= hi) hitIndexes.push(index)
  }
  if (hitIndexes.length > 0) {
    const start = hitIndexes[0]
    const end = hitIndexes[hitIndexes.length - 1]
    return slots.slice(start, end + 1).map((slot) => slot.path)
  }
  const midRange = (lo + hi) / 2
  let bestIndex = 0
  let bestDist = Infinity
  for (let index = 0; index < slots.length; index += 1) {
    const slot = slots[index]
    const mid = slot.y + slot.height / 2
    const dist = Math.abs(mid - midRange)
    if (dist < bestDist) {
      bestDist = dist
      bestIndex = index
    }
  }
  return [slots[bestIndex].path]
}

export function resolveConsecutiveSiblingRange(
  nodeIds: readonly string[],
  nodes: readonly DiagramNode[],
  connections: readonly Connection[]
): SiblingRangeResult {
  const ids = nodeIds.filter((id, index, list) => list.indexOf(id) === index)
  if (ids.length === 0) return { ok: false, reason: 'need-nodes' }
  if (ids.some((id) => isMindMapTopicId(id))) return { ok: false, reason: 'topic' }
  if (ids.some((id) => isMindMapSummaryNodeId(id))) return { ok: false, reason: 'summary' }

  const paths: string[] = []
  for (const id of ids) {
    const path = mindMapNodePathKey(id, connections as Connection[])
    if (!path || path === MINDMAP_TOPIC_ID) return { ok: false, reason: 'not-siblings' }
    paths.push(path)
  }
  if (!areConsecutiveSiblingPaths(paths)) {
    const prefix = pathParentPrefix(paths[0])
    const sameParent = prefix != null && paths.every((p) => pathParentPrefix(p) === prefix)
    return { ok: false, reason: sameParent ? 'not-consecutive' : 'not-siblings' }
  }
  return { ok: true, coveredPaths: sortSiblingPaths(paths) }
}

export function remapSummaryCoveredPaths(
  coveredPaths: readonly string[],
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  remapNodeId: (
    oldId: string,
    oldNodes: DiagramNode[],
    oldConnections: Connection[],
    newNodes: DiagramNode[],
    newConnections: Connection[]
  ) => string | null
): string[] {
  const next: string[] = []
  for (const path of coveredPaths) {
    const oldId = findNodeIdByPathKey(oldNodes, oldConnections, path)
    if (!oldId) continue
    const newId = remapNodeId(oldId, oldNodes, oldConnections, newNodes, newConnections)
    if (!newId) continue
    const newPath = mindMapNodePathKey(newId, newConnections)
    if (newPath && newPath !== MINDMAP_TOPIC_ID) next.push(newPath)
  }
  const unique = next.filter((p, i, list) => list.indexOf(p) === i)
  if (!areConsecutiveSiblingPaths(unique)) {
    return longestConsecutiveRun(unique)
  }
  return sortSiblingPaths(unique)
}

function longestConsecutiveRun(paths: readonly string[]): string[] {
  if (paths.length === 0) return []
  const byPrefix = new Map<string, string[]>()
  for (const path of paths) {
    const prefix = pathParentPrefix(path)
    if (prefix == null) continue
    const list = byPrefix.get(prefix) ?? []
    list.push(path)
    byPrefix.set(prefix, list)
  }
  let best: string[] = []
  for (const group of byPrefix.values()) {
    const sorted = sortSiblingPaths(group)
    let run: string[] = [sorted[0]]
    for (let i = 1; i < sorted.length; i += 1) {
      const prev = pathLastIndex(sorted[i - 1])
      const cur = pathLastIndex(sorted[i])
      if (prev != null && cur != null && cur === prev + 1) {
        run.push(sorted[i])
      } else {
        if (run.length > best.length) best = run
        run = [sorted[i]]
      }
    }
    if (run.length > best.length) best = run
  }
  return best
}

export function remapMindMapSummariesAfterReload(
  summaries: readonly MindMapSummarySpec[],
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  remapNodeId: (
    oldId: string,
    oldNodes: DiagramNode[],
    oldConnections: Connection[],
    newNodes: DiagramNode[],
    newConnections: Connection[]
  ) => string | null
): MindMapSummarySpec[] {
  const next: MindMapSummarySpec[] = []
  for (const summary of summaries) {
    const coveredPaths = remapSummaryCoveredPaths(
      summary.coveredPaths,
      oldNodes,
      oldConnections,
      newNodes,
      newConnections,
      remapNodeId
    )
    if (coveredPaths.length === 0) continue
    next.push({ ...summary, coveredPaths })
  }
  return next
}

export function filterTreeMindMapNodes(nodes: readonly DiagramNode[]): DiagramNode[] {
  return nodes.filter((node) => !isMindMapSummaryNode(node))
}

export function walkSummaryChildren(
  children: readonly MindMapSummaryChildSpec[] | undefined,
  visit: (child: MindMapSummaryChildSpec, indexPath: number[]) => void,
  prefix: number[] = []
): void {
  if (!children) return
  children.forEach((child, index) => {
    const path = [...prefix, index]
    visit(child, path)
    walkSummaryChildren(child.children, visit, path)
  })
}

export function updateSummaryChildText(
  children: MindMapSummaryChildSpec[] | undefined,
  indexPath: readonly number[],
  text: string
): MindMapSummaryChildSpec[] | undefined {
  if (!children || indexPath.length === 0) return children
  const [head, ...rest] = indexPath
  return children.map((child, index) => {
    if (index !== head) return child
    if (rest.length === 0) return { ...child, text }
    return { ...child, children: updateSummaryChildText(child.children, rest, text) }
  })
}

export function insertSummaryChildAt(
  children: MindMapSummaryChildSpec[] | undefined,
  parentPath: readonly number[],
  text: string,
  siblingOffset?: 'above' | 'below' | 'end'
): MindMapSummaryChildSpec[] {
  const nextChild: MindMapSummaryChildSpec = { text }
  if (parentPath.length === 0) {
    const list = [...(children ?? [])]
    if (siblingOffset === 'above') list.unshift(nextChild)
    else list.push(nextChild)
    return list
  }
  const [head, ...rest] = parentPath
  const list = [...(children ?? [])]
  if (rest.length === 0 && (siblingOffset === 'above' || siblingOffset === 'below')) {
    const at = siblingOffset === 'above' ? head : head + 1
    list.splice(at, 0, nextChild)
    return list
  }
  const target = list[head]
  if (!target) {
    list.push(nextChild)
    return list
  }
  list[head] = {
    ...target,
    children: insertSummaryChildAt(target.children, rest, text, siblingOffset ?? 'end'),
  }
  return list
}
