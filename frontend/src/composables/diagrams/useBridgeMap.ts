/**
 * useBridgeMap - Composable for Bridge Map layout and data management
 * Bridge maps show analogies: "A is to B as C is to D"
 */
import { computed, ref } from 'vue'

import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CENTER_Y,
  DEFAULT_LEVEL_HEIGHT,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_STEP_SPACING,
} from './layoutConfig'

interface AnalogyPair {
  id: string
  top: string
  bottom: string
  relation?: string
}

interface BridgeMapData {
  relatingFactor: string
  pairs: AnalogyPair[]
}

interface BridgeMapOptions {
  startX?: number
  centerY?: number
  pairSpacing?: number
  verticalGap?: number
  nodeWidth?: number
  nodeHeight?: number
}

export function useBridgeMap(options: BridgeMapOptions = {}) {
  const {
    startX = 150,
    centerY = DEFAULT_CENTER_Y,
    pairSpacing = DEFAULT_STEP_SPACING + 50, // 250px
    verticalGap = DEFAULT_LEVEL_HEIGHT, // 100px - import added below
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT - 5, // 45px
  } = options

  const data = ref<BridgeMapData | null>(null)

  // Convert bridge map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    data.value.pairs.forEach((pair, pairIndex) => {
      const x = startX + pairIndex * pairSpacing

      // Top node
      result.push({
        id: `pair-${pairIndex}-top`,
        type: 'branch',
        position: {
          x: x - nodeWidth / 2,
          y: centerY - verticalGap / 2 - nodeHeight,
        },
        data: {
          label: pair.top,
          nodeType: 'branch',
          diagramType: 'bridge_map',
          isDraggable: true,
          isSelectable: true,
          pairIndex,
          position: 'top',
        },
        draggable: true,
      })

      // Bottom node
      result.push({
        id: `pair-${pairIndex}-bottom`,
        type: 'branch',
        position: {
          x: x - nodeWidth / 2,
          y: centerY + verticalGap / 2,
        },
        data: {
          label: pair.bottom,
          nodeType: 'branch',
          diagramType: 'bridge_map',
          isDraggable: true,
          isSelectable: true,
          pairIndex,
          position: 'bottom',
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges - vertical relation lines and horizontal bridges
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    data.value.pairs.forEach((pair, pairIndex) => {
      // Vertical edge between top and bottom (the "is to" relation)
      result.push({
        id: `relation-${pairIndex}`,
        source: `pair-${pairIndex}-top`,
        target: `pair-${pairIndex}-bottom`,
        type: 'straight',
        data: {
          edgeType: 'straight' as const,
          label: pair.relation || 'is to',
          isRelation: true,
        },
        style: { stroke: '#e6a23c', strokeWidth: 3 },
      })

      // Bridge to next pair (the "as" connection)
      if (pairIndex < data.value!.pairs.length - 1) {
        // Connect top to next top
        result.push({
          id: `bridge-top-${pairIndex}`,
          source: `pair-${pairIndex}-top`,
          target: `pair-${pairIndex + 1}-top`,
          type: 'straight',
          data: {
            edgeType: 'straight' as const,
            label: 'as',
            isBridge: true,
          },
          style: { stroke: '#c0c4cc', strokeDasharray: '8,4' },
        })

        // Connect bottom to next bottom
        result.push({
          id: `bridge-bottom-${pairIndex}`,
          source: `pair-${pairIndex}-bottom`,
          target: `pair-${pairIndex + 1}-bottom`,
          type: 'straight',
          data: {
            edgeType: 'straight' as const,
            isBridge: true,
          },
          style: { stroke: '#c0c4cc', strokeDasharray: '8,4' },
        })
      }
    })

    return result
  })

  // Set bridge map data
  function setData(newData: BridgeMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    if (diagramNodes.length === 0) return

    // Group nodes into pairs (alternating top/bottom)
    const pairs: AnalogyPair[] = []

    for (let i = 0; i < diagramNodes.length; i += 2) {
      const topNode = diagramNodes[i]
      const bottomNode = diagramNodes[i + 1]

      if (topNode) {
        pairs.push({
          id: `pair-${pairs.length}`,
          top: topNode.text,
          bottom: bottomNode?.text || '',
          relation: 'is to',
        })
      }
    }

    data.value = {
      relatingFactor: 'is to / as',
      pairs,
    }
  }

  // Add new analogy pair
  function addPair(top: string, bottom: string, relation?: string) {
    if (!data.value) {
      data.value = {
        relatingFactor: 'is to / as',
        pairs: [],
      }
    }

    data.value.pairs.push({
      id: `pair-${Date.now()}`,
      top,
      bottom,
      relation: relation || 'is to',
    })
  }

  // Remove pair by index
  function removePair(index: number) {
    if (!data.value) return
    if (index >= 0 && index < data.value.pairs.length) {
      data.value.pairs.splice(index, 1)
    }
  }

  // Update pair
  function updatePair(
    index: number,
    updates: { top?: string; bottom?: string; relation?: string }
  ) {
    if (!data.value) return
    if (index < 0 || index >= data.value.pairs.length) return

    const pair = data.value.pairs[index]
    if (updates.top !== undefined) pair.top = updates.top
    if (updates.bottom !== undefined) pair.bottom = updates.bottom
    if (updates.relation !== undefined) pair.relation = updates.relation
  }

  // Update relating factor
  function setRelatingFactor(factor: string) {
    if (data.value) {
      data.value.relatingFactor = factor
    }
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addPair,
    removePair,
    updatePair,
    setRelatingFactor,
  }
}
