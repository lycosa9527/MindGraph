/**
 * useBraceMap - Composable for Brace Map layout and data management
 * Brace maps show part-whole relationships with braces
 *
 * Custom column-based layout (no Dagre dependency):
 * - Whole on the left
 * - Parts expand to the right in left-aligned columns
 * - Y positions computed bottom-up: leaves stack, parents center on children
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  BRACE_MAP_LEVEL_WIDTH,
  BRACE_MAP_NODE_SPACING,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from './layoutConfig'

interface BraceNode {
  id: string
  text: string
  parts?: BraceNode[]
}

interface BraceMapData {
  whole: BraceNode
}

interface BraceMapOptions {
  levelWidth?: number
  nodeSpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

interface FlatNode {
  id: string
  text: string
  depth: number
}

export function useBraceMap(options: BraceMapOptions = {}) {
  const {
    levelWidth = BRACE_MAP_LEVEL_WIDTH,
    nodeSpacing = BRACE_MAP_NODE_SPACING,
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options

  const { t } = useLanguage()
  const data = ref<BraceMapData | null>(null)

  function flattenBraceTree(
    node: BraceNode,
    depth: number,
    parentId: string | null,
    flatNodes: FlatNode[],
    edges: { source: string; target: string }[],
    counter: { value: number }
  ): void {
    const nodeId = node.id || `brace-${depth}-${counter.value++}`

    flatNodes.push({ id: nodeId, text: node.text, depth })

    if (parentId) {
      edges.push({ source: parentId, target: nodeId })
    }

    if (node.parts && node.parts.length > 0) {
      node.parts.forEach((part) => {
        flattenBraceTree(part, depth + 1, nodeId, flatNodes, edges, counter)
      })
    }
  }

  function computeColumnLayout(
    flatNodes: FlatNode[],
    edges: { source: string; target: string }[]
  ): Map<string, { x: number; y: number }> {
    const childrenMap = new Map<string, string[]>()
    for (const e of edges) {
      const kids = childrenMap.get(e.source)
      if (kids) kids.push(e.target)
      else childrenMap.set(e.source, [e.target])
    }

    // X: column positions (left-aligned per depth)
    const maxDepth = flatNodes.reduce((m, n) => Math.max(m, n.depth), 0)
    const columnX = new Map<number, number>()
    let x = DEFAULT_PADDING
    for (let d = 0; d <= maxDepth; d++) {
      columnX.set(d, x)
      x += nodeWidth + levelWidth
    }

    // Y: bottom-up recursive stacking
    const newY = new Map<string, number>()

    function computeSubtreeSpan(nid: string): number {
      const kids = childrenMap.get(nid)
      if (!kids || kids.length === 0) return nodeHeight
      const childSpans = kids.map(computeSubtreeSpan)
      const childrenTotal =
        childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * nodeSpacing
      return Math.max(nodeHeight, childrenTotal)
    }

    function assignSubtreeY(nid: string, startY: number): number {
      const kids = childrenMap.get(nid)

      if (!kids || kids.length === 0) {
        newY.set(nid, startY)
        return startY + nodeHeight
      }

      const childSpans = kids.map(computeSubtreeSpan)
      const childrenTotal =
        childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * nodeSpacing

      if (childrenTotal >= nodeHeight) {
        let y = startY
        for (let i = 0; i < kids.length; i++) {
          if (i > 0) y += nodeSpacing
          y = assignSubtreeY(kids[i], y)
        }
        const childTop = newY.get(kids[0]) ?? startY
        const lastKid = kids[kids.length - 1]
        const childBottom = (newY.get(lastKid) ?? startY) + nodeHeight
        const childCenter = (childTop + childBottom) / 2
        newY.set(nid, childCenter - nodeHeight / 2)
        return y
      }

      newY.set(nid, startY)
      const shift = (nodeHeight - childrenTotal) / 2
      let y = startY + shift
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) y += nodeSpacing
        y = assignSubtreeY(kids[i], y)
      }
      return startY + nodeHeight
    }

    const targetIds = new Set(edges.map((e) => e.target))
    const rootId = flatNodes.find((n) => !targetIds.has(n.id))?.id ?? flatNodes[0]?.id
    if (rootId) {
      assignSubtreeY(rootId, DEFAULT_PADDING)
    }

    const positions = new Map<string, { x: number; y: number }>()
    for (const n of flatNodes) {
      positions.set(n.id, {
        x: columnX.get(n.depth) ?? DEFAULT_PADDING,
        y: newY.get(n.id) ?? DEFAULT_PADDING,
      })
    }
    return positions
  }

  function generateLayout(): { nodes: MindGraphNode[]; edges: MindGraphEdge[] } {
    if (!data.value) return { nodes: [], edges: [] }

    const flatNodes: FlatNode[] = []
    const edges: { source: string; target: string }[] = []
    flattenBraceTree(data.value.whole, 0, null, flatNodes, edges, { value: 0 })

    const positions = computeColumnLayout(flatNodes, edges)

    const vfNodes: MindGraphNode[] = []
    for (const fn of flatNodes) {
      const pos = positions.get(fn.id)
      if (pos) {
        vfNodes.push({
          id: fn.id,
          type: fn.depth === 0 ? 'topic' : 'brace',
          position: pos,
          data: {
            label: fn.text,
            nodeType: fn.depth === 0 ? 'topic' : 'brace',
            diagramType: 'brace_map',
            isDraggable: fn.depth > 0,
            isSelectable: true,
          },
          draggable: fn.depth > 0,
        })
      }
    }

    const vfEdges: MindGraphEdge[] = edges.map((e) => ({
      id: `edge-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: 'brace',
      data: { edgeType: 'brace' as const },
    }))

    return { nodes: vfNodes, edges: vfEdges }
  }

  const nodes = computed<MindGraphNode[]>(() => {
    return generateLayout().nodes
  })

  const edges = computed<MindGraphEdge[]>(() => {
    return generateLayout().edges
  })

  function setData(newData: BraceMapData) {
    data.value = newData
  }

  function fromDiagramNodes(diagramNodes: DiagramNode[], connections: Connection[]) {
    if (diagramNodes.length === 0) return

    const targetIds = new Set(connections.map((c) => c.target))
    const rootNode =
      diagramNodes.find(
        (n) => !targetIds.has(n.id) && (n.type === 'topic' || n.type === 'center')
      ) ||
      diagramNodes.find((n) => !targetIds.has(n.id)) ||
      diagramNodes[0]

    function buildParts(parentId: string): BraceNode[] {
      const childConnections = connections.filter((c) => c.source === parentId)
      const result: BraceNode[] = []
      for (const c of childConnections) {
        const childNode = diagramNodes.find((n) => n.id === c.target)
        if (childNode) {
          const childParts = buildParts(childNode.id)
          result.push({
            id: childNode.id,
            text: childNode.text,
            parts: childParts.length > 0 ? childParts : undefined,
          })
        }
      }
      return result
    }

    data.value = {
      whole: {
        id: rootNode.id,
        text: rootNode.text,
        parts: buildParts(rootNode.id),
      },
    }
  }

  function addPart(parentId: string, text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    const targetParentId = selectedNodeId || parentId
    const partText = text || t('diagram.newPart', 'New Part')

    function findAndAdd(node: BraceNode): boolean {
      if (node.id === targetParentId) {
        if (!node.parts) {
          node.parts = []
        }
        node.parts.push({
          id: `brace-part-${Date.now()}`,
          text: partText,
        })
        return true
      }

      if (node.parts) {
        for (const part of node.parts) {
          if (findAndAdd(part)) return true
        }
      }
      return false
    }

    return findAndAdd(data.value.whole)
  }

  function removePart(partId: string) {
    if (!data.value || data.value.whole.id === partId) return

    function findAndRemove(parent: BraceNode): boolean {
      if (!parent.parts) return false

      const index = parent.parts.findIndex((p) => p.id === partId)
      if (index !== -1) {
        parent.parts.splice(index, 1)
        if (parent.parts.length === 0) {
          parent.parts = undefined
        }
        return true
      }

      for (const part of parent.parts) {
        if (findAndRemove(part)) return true
      }
      return false
    }

    findAndRemove(data.value.whole)
  }

  function updateText(nodeId: string, text: string) {
    if (!data.value) return

    function findAndUpdate(node: BraceNode): boolean {
      if (node.id === nodeId) {
        node.text = text
        return true
      }

      if (node.parts) {
        for (const part of node.parts) {
          if (findAndUpdate(part)) return true
        }
      }
      return false
    }

    findAndUpdate(data.value.whole)
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addPart,
    removePart,
    updateText,
  }
}
