/**
 * useMultiFlowMap - Composable for Multi-Flow Map layout and data management
 * Multi-flow maps show causes and effects of a central event
 *
 * Structure:
 * - Central event (non-draggable)
 * - Causes on the left side
 * - Effects on the right side
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'

interface MultiFlowMapData {
  event: string
  causes: string[]
  effects: string[]
}

interface MultiFlowMapOptions {
  centerX?: number
  centerY?: number
  sideSpacing?: number
  verticalSpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

export function useMultiFlowMap(options: MultiFlowMapOptions = {}) {
  const {
    centerX = DEFAULT_CENTER_X,
    centerY = DEFAULT_CENTER_Y,
    sideSpacing = 200,
    verticalSpacing = DEFAULT_VERTICAL_SPACING + 10, // 70px
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options

  const { t } = useLanguage()
  const data = ref<MultiFlowMapData | null>(null)

  // Convert multi-flow map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central event node
    result.push({
      id: 'event',
      type: 'topic',
      position: { x: centerX - nodeWidth / 2, y: centerY - nodeHeight / 2 },
      data: {
        label: data.value.event,
        nodeType: 'topic',
        diagramType: 'multi_flow_map',
        isDraggable: false,
        isSelectable: true,
        causeCount: data.value.causes.length, // Pass cause count for handle generation
        effectCount: data.value.effects.length, // Pass effect count for handle generation
      },
      draggable: false,
    })

    // Causes on the left (stacked vertically)
    const causeCount = data.value.causes.length
    const causeStartY = centerY - ((causeCount - 1) * verticalSpacing) / 2
    data.value.causes.forEach((cause, index) => {
      result.push({
        id: `cause-${index}`,
        type: 'flow',
        position: {
          x: centerX - sideSpacing - nodeWidth / 2,
          y: causeStartY + index * verticalSpacing - nodeHeight / 2,
        },
        data: {
          label: cause,
          nodeType: 'flow',
          diagramType: 'multi_flow_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    // Effects on the right (stacked vertically)
    const effectCount = data.value.effects.length
    const effectStartY = centerY - ((effectCount - 1) * verticalSpacing) / 2
    data.value.effects.forEach((effect, index) => {
      result.push({
        id: `effect-${index}`,
        type: 'flow',
        position: {
          x: centerX + sideSpacing - nodeWidth / 2,
          y: effectStartY + index * verticalSpacing - nodeHeight / 2,
        },
        data: {
          label: effect,
          nodeType: 'flow',
          diagramType: 'multi_flow_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges with arrows
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Edges from causes to event (arrows pointing to event)
    // Connect from cause's right handle to topic's specific left handle (left-0, left-1, etc.)
    data.value.causes.forEach((_, index) => {
      result.push({
        id: `edge-cause-${index}`,
        source: `cause-${index}`,
        target: 'event',
        type: 'straight',
        sourceHandle: 'right',
        targetHandle: `left-${index}`, // Use specific handle ID matching the cause index
        data: {
          edgeType: 'straight' as const,
          animated: false,
        },
      })
    })

    // Edges from event to effects (arrows pointing to effects)
    // Connect from topic's specific right handle to effect's left handle
    data.value.effects.forEach((_, index) => {
      result.push({
        id: `edge-effect-${index}`,
        source: 'event',
        target: `effect-${index}`,
        type: 'straight',
        sourceHandle: `right-${index}`, // Use specific handle ID matching the effect index
        targetHandle: 'left',
        data: {
          edgeType: 'straight' as const,
          animated: false,
        },
      })
    })

    return result
  })

  // Set data
  function setData(newData: MultiFlowMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const eventNode = diagramNodes.find((n) => n.id === 'event' || n.type === 'topic')
    const causeNodes = diagramNodes.filter((n) => n.id?.startsWith('cause-'))
    const effectNodes = diagramNodes.filter((n) => n.id?.startsWith('effect-'))

    data.value = {
      event: eventNode?.text || '',
      causes: causeNodes.map((n) => n.text),
      effects: effectNodes.map((n) => n.text),
    }
  }

  // Add a cause (requires selection context)
  function addCause(text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Cannot add from event node
    if (selectedNodeId === 'event') {
      console.warn('Cannot add to central event directly')
      return false
    }

    // Validate selection is a cause if provided
    if (selectedNodeId && !selectedNodeId.startsWith('cause-')) {
      console.warn('Please select a cause to add a new cause')
      return false
    }

    const causeText = text || t('diagram.newCause', 'New Cause')
    data.value.causes.push(causeText)
    return true
  }

  // Add an effect (requires selection context)
  function addEffect(text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Cannot add from event node
    if (selectedNodeId === 'event') {
      console.warn('Cannot add to central event directly')
      return false
    }

    // Validate selection is an effect if provided
    if (selectedNodeId && !selectedNodeId.startsWith('effect-')) {
      console.warn('Please select an effect to add a new effect')
      return false
    }

    const effectText = text || t('diagram.newEffect', 'New Effect')
    data.value.effects.push(effectText)
    return true
  }

  // Remove a cause
  function removeCause(index: number) {
    if (data.value && index >= 0 && index < data.value.causes.length) {
      data.value.causes.splice(index, 1)
    }
  }

  // Remove an effect
  function removeEffect(index: number) {
    if (data.value && index >= 0 && index < data.value.effects.length) {
      data.value.effects.splice(index, 1)
    }
  }

  // Update cause text
  function updateCause(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.causes.length) {
      data.value.causes[index] = text
    }
  }

  // Update effect text
  function updateEffect(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.effects.length) {
      data.value.effects[index] = text
    }
  }

  // Update event text
  function updateEvent(text: string) {
    if (data.value) {
      data.value.event = text
    }
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addCause,
    addEffect,
    removeCause,
    removeEffect,
    updateCause,
    updateEffect,
    updateEvent,
  }
}
