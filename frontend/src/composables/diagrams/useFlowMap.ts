/**
 * useFlowMap - Composable for Flow Map layout and data management
 * Flow maps show sequential steps in a process
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

interface FlowStep {
  id: string
  text: string
  description?: string
}

interface FlowMapData {
  title?: string
  steps: FlowStep[]
}

interface FlowMapOptions {
  startX?: number
  centerY?: number
  stepSpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

export function useFlowMap(options: FlowMapOptions = {}) {
  const {
    startX = 100,
    centerY = 300,
    stepSpacing = 200,
    nodeWidth = 140,
    nodeHeight = 60,
  } = options

  const { t } = useLanguage()
  const data = ref<FlowMapData | null>(null)

  // Convert flow map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    return data.value.steps.map((step, index) => {
      const x = startX + index * stepSpacing

      return {
        id: step.id || `flow-step-${index}`,
        type: 'flow',
        position: { x: x - nodeWidth / 2, y: centerY - nodeHeight / 2 },
        data: {
          label: step.text,
          nodeType: 'flow',
          diagramType: 'flow_map',
          isDraggable: true,
          isSelectable: true,
          // Store step number for display
          stepNumber: index + 1,
        },
        draggable: true,
      } as MindGraphNode
    })
  })

  // Generate edges with arrows
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value || data.value.steps.length < 2) return []

    const result: MindGraphEdge[] = []

    for (let i = 0; i < data.value.steps.length - 1; i++) {
      const sourceId = data.value.steps[i].id || `flow-step-${i}`
      const targetId = data.value.steps[i + 1].id || `flow-step-${i + 1}`

      result.push({
        id: `edge-${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        type: 'straight',
        data: {
          edgeType: 'straight' as const,
          animated: true,
        },
      })
    }

    return result
  })

  // Set flow map data
  function setData(newData: FlowMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], connections: Connection[]) {
    if (diagramNodes.length === 0) return

    // Order nodes based on connections
    const orderedNodes = orderNodes(diagramNodes, connections)

    data.value = {
      steps: orderedNodes.map((node) => ({
        id: node.id,
        text: node.text,
      })),
    }
  }

  // Order nodes by following connection chain
  function orderNodes(nodes: DiagramNode[], connections: Connection[]): DiagramNode[] {
    if (connections.length === 0) return nodes

    // Build next node map
    const next = new Map<string, string>()
    connections.forEach((c) => next.set(c.source, c.target))

    // Find start node (no incoming connection)
    const targets = new Set(connections.map((c) => c.target))
    let currentId = nodes.find((n) => !targets.has(n.id))?.id || nodes[0]?.id

    const ordered: DiagramNode[] = []
    const visited = new Set<string>()

    while (currentId && !visited.has(currentId)) {
      const node = nodes.find((n) => n.id === currentId)
      if (node) {
        ordered.push(node)
        visited.add(currentId)
      }
      currentId = next.get(currentId) || ''
    }

    // Add remaining nodes not in chain
    nodes.forEach((n) => {
      if (!visited.has(n.id)) ordered.push(n)
    })

    return ordered
  }

  // Add step at position (requires selection context matching old JS behavior)
  function addStep(text?: string, position?: number, selectedNodeId?: string): boolean {
    if (!data.value) {
      data.value = { steps: [] }
    }

    // Selection validation (matching old JS behavior)
    // For flow maps, you can add steps without selection, but if selection is provided,
    // ensure it's a valid step (not title)
    if (selectedNodeId && selectedNodeId.startsWith('title')) {
      console.warn('Cannot add steps to title')
      return false
    }

    // Use default translated text if not provided (matching old JS behavior)
    const stepText = text || t('diagram.newStep', 'New Step')

    const newStep: FlowStep = {
      id: `flow-step-${Date.now()}`,
      text: stepText,
    }

    // If selectedNodeId is provided, insert after that step
    if (selectedNodeId && !selectedNodeId.startsWith('title')) {
      const selectedIndex = data.value.steps.findIndex((s) => s.id === selectedNodeId)
      if (selectedIndex !== -1) {
        data.value.steps.splice(selectedIndex + 1, 0, newStep)
        return true
      }
    }

    // Otherwise use position parameter or append
    if (position !== undefined && position >= 0 && position <= data.value.steps.length) {
      data.value.steps.splice(position, 0, newStep)
    } else {
      data.value.steps.push(newStep)
    }
    return true
  }

  // Remove step by id or index
  function removeStep(idOrIndex: string | number) {
    if (!data.value) return

    if (typeof idOrIndex === 'number') {
      if (idOrIndex >= 0 && idOrIndex < data.value.steps.length) {
        data.value.steps.splice(idOrIndex, 1)
      }
    } else {
      const index = data.value.steps.findIndex((s) => s.id === idOrIndex)
      if (index !== -1) {
        data.value.steps.splice(index, 1)
      }
    }
  }

  // Update step text
  function updateStep(idOrIndex: string | number, text: string) {
    if (!data.value) return

    let step: FlowStep | undefined

    if (typeof idOrIndex === 'number') {
      step = data.value.steps[idOrIndex]
    } else {
      step = data.value.steps.find((s) => s.id === idOrIndex)
    }

    if (step) {
      step.text = text
    }
  }

  // Reorder steps
  function reorderSteps(fromIndex: number, toIndex: number) {
    if (!data.value) return
    if (fromIndex < 0 || fromIndex >= data.value.steps.length) return
    if (toIndex < 0 || toIndex >= data.value.steps.length) return

    const [step] = data.value.steps.splice(fromIndex, 1)
    data.value.steps.splice(toIndex, 0, step)
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addStep,
    removeStep,
    updateStep,
    reorderSteps,
  }
}
