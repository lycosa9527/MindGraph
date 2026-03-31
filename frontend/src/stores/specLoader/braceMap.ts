/**
 * Brace Map Loader
 *
 * Custom column-based layout (like mind map) using actual DOM-measured
 * dimensions from Pinia store. No Dagre dependency.
 *
 * X: Each depth level forms a left-aligned column. Column X chains outward
 *    from the root using max-width-per-depth + rank gap.
 * Y: Bottom-up recursive stacking -- leaf nodes stack with sibling gap,
 *    parents vertically center on their children.
 */
import {
  BRACE_MAP_LEVEL_WIDTH,
  BRACE_MAP_NODE_SPACING,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureTextWidth,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'

interface BraceNode {
  id?: string
  text: string
  parts?: BraceNode[]
}

const BRACE_TOPIC_FONT_SIZE = 18
const BRACE_PART_FONT_SIZE = 16
const BRACE_SUBPART_FONT_SIZE = 12
const BRACE_TOPIC_PADDING_X = 48 + 6 // px-6 (24*2) + border (3*2)
const BRACE_PILL_PADDING_X = 40 + 4 // px-5 (20*2) + border (2*2)
const BRACE_MAX_NODE_WIDTH = 280
const BRACE_NODE_MAX_TEXT_WIDTH = 240
const BRACE_TOPIC_MAX_TEXT_WIDTH = 300

function getBraceFontSize(depth: number): number {
  if (depth === 0) return BRACE_TOPIC_FONT_SIZE
  if (depth === 1) return BRACE_PART_FONT_SIZE
  return BRACE_SUBPART_FONT_SIZE
}

function estimateBraceNodeWidth(text: string, depth: number): number {
  const trimmed = (text || '').trim()
  const fontSize = getBraceFontSize(depth)
  const paddingX = depth === 0 ? BRACE_TOPIC_PADDING_X : BRACE_PILL_PADDING_X

  let textWidth = 0
  if (typeof document !== 'undefined') {
    textWidth = measureTextWidth(trimmed || ' ', fontSize)
    if (depth === 0) {
      textWidth *= 1.08
    }
  }

  const width = Math.ceil(textWidth + paddingX)
  return Math.max(
    NODE_MIN_DIMENSIONS.brace.minWidth,
    Math.min(BRACE_MAX_NODE_WIDTH, width || DEFAULT_NODE_WIDTH)
  )
}

/**
 * Estimate node height accounting for text wrapping and KaTeX formulas.
 * InlineEditableText max-width is 240px (brace) / 300px (topic).
 * When measured text exceeds that, lines wrap and height grows.
 * For KaTeX labels the rendered DOM height is measured directly so the
 * layout doesn't rely on inaccurate plain-text heuristics.
 */
function estimateBraceNodeHeight(text: string, depth: number): number {
  const trimmed = (text || '').trim()
  if (!trimmed || typeof document === 'undefined') return DEFAULT_NODE_HEIGHT

  const fontSize = getBraceFontSize(depth)
  const maxTextWidth = depth === 0 ? BRACE_TOPIC_MAX_TEXT_WIDTH : BRACE_NODE_MAX_TEXT_WIDTH
  const paddingY = depth === 0 ? 32 : 16

  if (diagramLabelLikelyNeedsRenderedMeasure(trimmed)) {
    const contentH = measureRenderedDiagramLabelHeight(trimmed, fontSize, maxTextWidth, {
      fontWeight: depth === 0 ? 'bold' : 'normal',
    })
    const h = Math.max(DEFAULT_NODE_HEIGHT, Math.ceil(contentH + paddingY))
    console.log(`[NodeLayout:Estimate] BraceNode text="${trimmed.slice(0, 40)}" depth=${depth} contentH=${contentH} paddingY=${paddingY} → h=${h} (KaTeX)`)
    return h
  }

  const textWidth = measureTextWidth(trimmed, fontSize)
  if (textWidth <= maxTextWidth) {
    console.log(`[NodeLayout:Estimate] BraceNode text="${trimmed.slice(0, 40)}" depth=${depth} → h=${DEFAULT_NODE_HEIGHT} (single-line)`)
    return DEFAULT_NODE_HEIGHT
  }

  const lineHeight = fontSize * 1.5
  const numLines = Math.ceil(textWidth / maxTextWidth)
  const h = Math.max(DEFAULT_NODE_HEIGHT, Math.ceil(numLines * lineHeight + paddingY))
  console.log(`[NodeLayout:Estimate] BraceNode text="${trimmed.slice(0, 40)}" depth=${depth} numLines=${numLines} → h=${h} (wrapped)`)
  return h
}

// ---------------------------------------------------------------------------
// Flatten tree
// ---------------------------------------------------------------------------

interface FlatNode {
  id: string
  text: string
  depth: number
  width: number
  height: number
}

function flattenTree(
  node: BraceNode,
  depth: number,
  parentId: string | null,
  nodes: FlatNode[],
  edges: { source: string; target: string }[],
  counter: { value: number }
): string {
  const nodeId = node.id || `brace-${depth}-${counter.value++}`
  const nodeWidth = estimateBraceNodeWidth(node.text, depth)
  const nodeHeight = estimateBraceNodeHeight(node.text, depth)

  nodes.push({ id: nodeId, text: node.text, depth, width: nodeWidth, height: nodeHeight })

  if (parentId) {
    edges.push({ source: parentId, target: nodeId })
  }

  if (node.parts && node.parts.length > 0) {
    node.parts.forEach((part) => {
      flattenTree(part, depth + 1, nodeId, nodes, edges, counter)
    })
  }

  return nodeId
}

// ---------------------------------------------------------------------------
// Custom column layout (replaces Dagre)
// ---------------------------------------------------------------------------

interface LayoutResult {
  positions: Map<string, { x: number; y: number }>
}

function computeColumnLayout(
  flatNodes: FlatNode[],
  edges: { source: string; target: string }[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): LayoutResult {
  const nodeMap = new Map<string, FlatNode>()
  for (const n of flatNodes) nodeMap.set(n.id, n)

  const childrenMap = new Map<string, string[]>()
  for (const e of edges) {
    const kids = childrenMap.get(e.source)
    if (kids) kids.push(e.target)
    else childrenMap.set(e.source, [e.target])
  }

  const getW = (id: string): number =>
    nodeDimensions[id]?.width ?? nodeMap.get(id)?.width ?? DEFAULT_NODE_WIDTH
  const getH = (id: string): number => {
    const pinia = nodeDimensions[id]?.height
    const est = nodeMap.get(id)?.height
    const h = pinia ?? est ?? DEFAULT_NODE_HEIGHT
    const src = pinia != null ? 'pinia' : est != null ? 'estimate' : 'DEFAULT'
    console.log(`[NodeLayout:getH] id="${id}" h=${h} src=${src} (pinia=${pinia} est=${est})`)
    return h
  }

  // --- X: column positions (left-aligned per depth) ---
  const maxDepth = flatNodes.reduce((m, n) => Math.max(m, n.depth), 0)
  const maxWidthByDepth = new Map<number, number>()
  for (const n of flatNodes) {
    const w = getW(n.id)
    maxWidthByDepth.set(n.depth, Math.max(maxWidthByDepth.get(n.depth) ?? 0, w))
  }

  const columnX = new Map<number, number>()
  let x = DEFAULT_PADDING
  for (let d = 0; d <= maxDepth; d++) {
    columnX.set(d, x)
    x += (maxWidthByDepth.get(d) ?? DEFAULT_NODE_WIDTH) + BRACE_MAP_LEVEL_WIDTH
  }

  // --- Y: bottom-up recursive stacking ---
  const newY = new Map<string, number>()

  function computeSubtreeSpan(nodeId: string): number {
    const h = getH(nodeId)
    const kids = childrenMap.get(nodeId)
    if (!kids || kids.length === 0) return h
    const childSpans = kids.map(computeSubtreeSpan)
    const childrenTotal =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * BRACE_MAP_NODE_SPACING
    return Math.max(h, childrenTotal)
  }

  function assignSubtreeY(nodeId: string, startY: number): number {
    const h = getH(nodeId)
    const kids = childrenMap.get(nodeId)

    if (!kids || kids.length === 0) {
      newY.set(nodeId, startY)
      return startY + h
    }

    const childSpans = kids.map(computeSubtreeSpan)
    const childrenTotal =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * BRACE_MAP_NODE_SPACING

    if (childrenTotal >= h) {
      let y = startY
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) y += BRACE_MAP_NODE_SPACING
        y = assignSubtreeY(kids[i], y)
      }
      const childTop = newY.get(kids[0]) ?? startY
      const lastKid = kids[kids.length - 1]
      const lastKidH = getH(lastKid)
      const childBottom = (newY.get(lastKid) ?? startY) + lastKidH
      const childCenter = (childTop + childBottom) / 2
      newY.set(nodeId, childCenter - h / 2)
      return y
    }

    newY.set(nodeId, startY)
    const shift = (h - childrenTotal) / 2
    let y = startY + shift
    for (let i = 0; i < kids.length; i++) {
      if (i > 0) y += BRACE_MAP_NODE_SPACING
      y = assignSubtreeY(kids[i], y)
    }
    return startY + h
  }

  // Find root (node with no incoming edge)
  const targetIds = new Set(edges.map((e) => e.target))
  const rootId = flatNodes.find((n) => !targetIds.has(n.id))?.id ?? flatNodes[0]?.id
  if (rootId) {
    assignSubtreeY(rootId, DEFAULT_PADDING)
  }

  // Build final positions
  // Leaf (children) nodes → left-aligned within their column
  // Non-leaf (brace/part) nodes → center-aligned within their column
  const positions = new Map<string, { x: number; y: number }>()
  for (const n of flatNodes) {
    const baseX = columnX.get(n.depth) ?? DEFAULT_PADDING
    const kids = childrenMap.get(n.id)
    const isLeaf = !kids || kids.length === 0
    let nodeX: number
    if (isLeaf) {
      nodeX = baseX
    } else {
      const w = getW(n.id)
      const maxW = maxWidthByDepth.get(n.depth) ?? DEFAULT_NODE_WIDTH
      nodeX = baseX + (maxW - w) / 2
    }
    positions.set(n.id, {
      x: nodeX,
      y: newY.get(n.id) ?? DEFAULT_PADDING,
    })
  }

  return { positions }
}

// ---------------------------------------------------------------------------
// Group index (color scheme)
// ---------------------------------------------------------------------------

function computeGroupIndices(
  flatNodes: FlatNode[],
  edges: { source: string; target: string }[]
): Map<string, number> {
  const targetIds = new Set(edges.map((e) => e.target))
  const rootId = flatNodes.find((n) => !targetIds.has(n.id))?.id

  const childrenMap = new Map<string, string[]>()
  for (const e of edges) {
    const kids = childrenMap.get(e.source)
    if (kids) kids.push(e.target)
    else childrenMap.set(e.source, [e.target])
  }

  const groupIndexMap = new Map<string, number>()
  if (!rootId) return groupIndexMap

  const rootChildren = childrenMap.get(rootId) ?? []
  rootChildren.forEach((childId, idx) => {
    groupIndexMap.set(childId, idx)
  })

  // Propagate parent group index to descendants
  function propagate(nodeId: string): void {
    const kids = childrenMap.get(nodeId) ?? []
    const parentGroup = groupIndexMap.get(nodeId)
    for (const kid of kids) {
      if (parentGroup !== undefined && !groupIndexMap.has(kid)) {
        groupIndexMap.set(kid, parentGroup)
      }
      propagate(kid)
    }
  }

  for (const child of rootChildren) {
    propagate(child)
  }

  return groupIndexMap
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function loadBraceMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  let wholeNode: BraceNode | undefined

  if (typeof spec.whole === 'object' && spec.whole !== null) {
    wholeNode = spec.whole as BraceNode
  } else if (typeof spec.whole === 'string') {
    const parts = spec.parts as
      | Array<{ name: string; subparts?: Array<{ name: string }> }>
      | undefined
    wholeNode = {
      id: 'brace-whole',
      text: spec.whole,
      parts: parts?.map((p, i) => ({
        id: `brace-part-${i}`,
        text: p.name || '',
        parts: p.subparts?.map((sp, j) => ({
          id: `brace-subpart-${i}-${j}`,
          text: sp.name || '',
        })),
      })),
    }
  }

  if (wholeNode) {
    const flatNodes: FlatNode[] = []
    const edges: { source: string; target: string }[] = []
    flattenTree(wholeNode, 0, null, flatNodes, edges, { value: 0 })

    const layout = computeColumnLayout(flatNodes, edges)
    const groupIndexMap = computeGroupIndices(flatNodes, edges)

    for (const fn of flatNodes) {
      const pos = layout.positions.get(fn.id)
      const groupIndex = groupIndexMap.get(fn.id)
      const node: DiagramNode = {
        id: fn.id,
        text: fn.text || '',
        type: fn.depth === 0 ? 'topic' : 'brace',
        position: pos ?? { x: DEFAULT_PADDING, y: DEFAULT_PADDING },
        data: {
          estimatedWidth: fn.width,
          estimatedHeight: fn.height,
        },
      }
      if (groupIndex !== undefined) {
        const color = getMindmapBranchColor(groupIndex)
        node.data = { ...node.data, groupIndex }
        node.style = { backgroundColor: color.fill, borderColor: color.border }
      }
      nodes.push(node)
    }

    for (const edge of edges) {
      connections.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
      })
    }

    const dimension = spec.dimension as string | undefined
    if (dimension !== undefined) {
      const rootNode = flatNodes.find((n) => n.depth === 0)
      const rootPos = rootNode ? layout.positions.get(rootNode.id) : undefined
      const rootW = rootNode?.width ?? DEFAULT_NODE_WIDTH
      const rootH = rootNode?.height ?? DEFAULT_NODE_HEIGHT
      const topicCenterX = (rootPos?.x ?? DEFAULT_PADDING) + rootW / 2
      const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: (rootPos?.y ?? DEFAULT_PADDING) + rootH + 20,
        },
      })
    }
  }

  const dimension = spec.dimension as string | undefined
  return {
    nodes,
    connections,
    metadata: {
      dimension,
      alternativeDimensions: spec.alternative_dimensions as string[] | undefined,
    },
  }
}

/**
 * Recalculate brace map layout using column-based positioning and
 * actual DOM-measured dimensions from Pinia store.
 */
export function recalculateBraceMapLayout(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  const labelNode = nodes.find((n) => n.type === 'label' || n.id === 'dimension-label')
  const treeNodes = nodes.filter((n) => n.type !== 'label' && n.id !== 'dimension-label')
  if (treeNodes.length === 0) return nodes

  const targetIds = new Set(connections.map((c) => c.target))
  const rootNode = treeNodes.find((n) => !targetIds.has(n.id)) || treeNodes[0]
  const rootId = rootNode.id

  // Build tree and flatten
  const childrenMap = new Map<string, string[]>()
  connections.forEach((conn) => {
    if (!childrenMap.has(conn.source)) childrenMap.set(conn.source, [])
    const children = childrenMap.get(conn.source)
    if (children) {
      children.push(conn.target)
    }
  })

  function buildTree(nodeId: string): BraceNode {
    const node = treeNodes.find((n) => n.id === nodeId)
    const childIds = childrenMap.get(nodeId) ?? []
    const parts = childIds.map((id) => buildTree(id))
    return {
      id: nodeId,
      text: node?.text ?? '',
      parts: parts.length > 0 ? parts : undefined,
    }
  }

  const wholeNode = buildTree(rootId)
  const flatNodes: FlatNode[] = []
  const edges: { source: string; target: string }[] = []
  flattenTree(wholeNode, 0, null, flatNodes, edges, { value: 0 })

  console.log('[NodeLayout:BraceMap] recalculateBraceMapLayout called', {
    nodeCount: treeNodes.length,
    nodeDimensionKeys: Object.keys(nodeDimensions),
    nodeDimensions: { ...nodeDimensions },
  })
  for (const fn of flatNodes) {
    console.log(`[NodeLayout:BraceMap] flatNode id="${fn.id}" text="${fn.text}" depth=${fn.depth} estW=${fn.width} estH=${fn.height}`)
  }

  const layout = computeColumnLayout(flatNodes, edges, nodeDimensions)
  const groupIndexMap = computeGroupIndices(flatNodes, edges)

  const nodeMap = new Map(treeNodes.map((n) => [n.id, { ...n }]))
  for (const fn of flatNodes) {
    const pos = layout.positions.get(fn.id)
    const node = nodeMap.get(fn.id)
    if (node && pos) {
      console.log(`[NodeLayout:BraceMap] FINAL id="${fn.id}" pos=(${pos.x}, ${pos.y}) piniaH=${nodeDimensions[fn.id]?.height} estH=${fn.height}`)
      node.position = pos
      const groupIndex = groupIndexMap.get(fn.id)
      if (groupIndex !== undefined) {
        const color = getMindmapBranchColor(groupIndex)
        node.data = { ...node.data, groupIndex }
        node.style = { ...node.style, backgroundColor: color.fill, borderColor: color.border }
      }
    }
  }

  let result = Array.from(nodeMap.values())

  if (labelNode) {
    const rootFlatNode = flatNodes.find((n) => n.depth === 0)
    const rootPos = rootFlatNode ? layout.positions.get(rootFlatNode.id) : undefined
    const rootW = nodeDimensions[rootId]?.width ?? rootFlatNode?.width ?? DEFAULT_NODE_WIDTH
    const rootH = nodeDimensions[rootId]?.height ?? rootFlatNode?.height ?? DEFAULT_NODE_HEIGHT
    const topicCenterX = (rootPos?.x ?? DEFAULT_PADDING) + rootW / 2
    const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
    result = [
      ...result,
      {
        ...labelNode,
        position: {
          x: topicCenterX - labelWidth / 2,
          y: (rootPos?.y ?? DEFAULT_PADDING) + rootH + 20,
        },
      },
    ]
  }

  return result
}
