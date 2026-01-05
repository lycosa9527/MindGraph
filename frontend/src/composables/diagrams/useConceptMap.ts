/**
 * useConceptMap - Composable for Concept Map layout and data management
 * Concept maps show relationships between concepts with labeled connections
 *
 * Structure:
 * - Concepts (freeform nodes with positions)
 * - Connections with labels (relationships between concepts)
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

interface ConceptNode {
  id: string
  text: string
  x: number
  y: number
}

interface ConceptConnection {
  id: string
  from: string
  to: string
  label?: string
}

interface ConceptMapData {
  topic?: string
  concepts: ConceptNode[]
  connections: ConceptConnection[]
}

interface ConceptMapOptions {
  defaultX?: number
  defaultY?: number
  nodeWidth?: number
  nodeHeight?: number
}

export function useConceptMap(options: ConceptMapOptions = {}) {
  const { defaultX = 400, defaultY = 300, nodeWidth = 100, nodeHeight = 40 } = options

  const { t } = useLanguage()
  const data = ref<ConceptMapData | null>(null)

  // Counter for generating unique IDs
  let nodeIdCounter = 0

  // Generate unique node ID
  function generateNodeId(): string {
    return `concept-${Date.now()}-${nodeIdCounter++}`
  }

  // Convert concept map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Add topic node if exists
    if (data.value.topic) {
      result.push({
        id: 'topic',
        type: 'topic',
        position: { x: defaultX - nodeWidth / 2, y: 100 },
        data: {
          label: data.value.topic,
          nodeType: 'topic',
          diagramType: 'concept_map',
          isDraggable: false,
          isSelectable: true,
        },
        draggable: false,
      })
    }

    // Add concept nodes
    data.value.concepts.forEach((concept) => {
      result.push({
        id: concept.id,
        type: 'branch', // Use branch type for concept nodes
        position: { x: concept.x - nodeWidth / 2, y: concept.y - nodeHeight / 2 },
        data: {
          label: concept.text,
          nodeType: 'branch',
          diagramType: 'concept_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges with labels
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    return data.value.connections.map((conn) => ({
      id: conn.id,
      source: conn.from,
      target: conn.to,
      type: 'curved',
      label: conn.label,
      data: {
        edgeType: 'curved' as const,
        label: conn.label,
      },
    }))
  })

  // Set data
  function setData(newData: ConceptMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes and connections
  function fromDiagramNodes(diagramNodes: DiagramNode[], connections: Connection[]) {
    const topicNode = diagramNodes.find((n) => n.type === 'topic' || n.type === 'center')
    const conceptNodes = diagramNodes.filter((n) => n.type !== 'topic' && n.type !== 'center')

    data.value = {
      topic: topicNode?.text,
      concepts: conceptNodes.map((n) => ({
        id: n.id,
        text: n.text,
        x: n.position?.x || defaultX,
        y: n.position?.y || defaultY,
      })),
      connections: connections.map((c) => ({
        id: c.id,
        from: c.source,
        to: c.target,
        label: c.label,
      })),
    }
  }

  // Add a new concept node
  function addConcept(text?: string, x?: number, y?: number): string {
    if (!data.value) {
      data.value = { concepts: [], connections: [] }
    }

    const conceptText = text || t('diagram.newConcept', 'New Concept')
    const newConcept: ConceptNode = {
      id: generateNodeId(),
      text: conceptText,
      x: x ?? defaultX + Math.random() * 100 - 50,
      y: y ?? defaultY + Math.random() * 100 - 50,
    }

    data.value.concepts.push(newConcept)
    return newConcept.id
  }

  // Remove a concept and its connections
  function removeConcept(conceptId: string): boolean {
    if (!data.value) return false

    // Cannot remove topic
    if (conceptId === 'topic') {
      console.warn('Cannot remove topic node')
      return false
    }

    const index = data.value.concepts.findIndex((c) => c.id === conceptId)
    if (index === -1) return false

    // Remove the concept
    data.value.concepts.splice(index, 1)

    // Remove connections involving this concept
    data.value.connections = data.value.connections.filter(
      (c) => c.from !== conceptId && c.to !== conceptId
    )

    return true
  }

  // Update concept text
  function updateConceptText(conceptId: string, text: string): boolean {
    if (!data.value) return false

    const concept = data.value.concepts.find((c) => c.id === conceptId)
    if (!concept) return false

    // Update text in concept
    const oldText = concept.text
    concept.text = text

    // Update connections that reference this concept by old text
    // (for backwards compatibility with text-based lookups)
    data.value.connections.forEach((conn) => {
      if (conn.from === oldText) conn.from = text
      if (conn.to === oldText) conn.to = text
    })

    return true
  }

  // Update concept position
  function updateConceptPosition(conceptId: string, x: number, y: number): boolean {
    if (!data.value) return false

    const concept = data.value.concepts.find((c) => c.id === conceptId)
    if (!concept) return false

    concept.x = x
    concept.y = y
    return true
  }

  // Add a connection between two concepts
  function addConnection(fromId: string, toId: string, label?: string): string | null {
    if (!data.value) return null

    // Check if both concepts exist
    const fromExists = fromId === 'topic' || data.value.concepts.some((c) => c.id === fromId)
    const toExists = toId === 'topic' || data.value.concepts.some((c) => c.id === toId)

    if (!fromExists || !toExists) {
      console.warn('Both concepts must exist to create a connection')
      return null
    }

    // Check if connection already exists
    const exists = data.value.connections.some((c) => c.from === fromId && c.to === toId)
    if (exists) {
      console.warn('Connection already exists')
      return null
    }

    const newConnection: ConceptConnection = {
      id: `conn-${Date.now()}`,
      from: fromId,
      to: toId,
      label: label || '',
    }

    data.value.connections.push(newConnection)
    return newConnection.id
  }

  // Remove a connection
  function removeConnection(connectionId: string): boolean {
    if (!data.value) return false

    const index = data.value.connections.findIndex((c) => c.id === connectionId)
    if (index === -1) return false

    data.value.connections.splice(index, 1)
    return true
  }

  // Update connection label
  function updateConnectionLabel(connectionId: string, label: string): boolean {
    if (!data.value) return false

    const connection = data.value.connections.find((c) => c.id === connectionId)
    if (!connection) return false

    connection.label = label
    return true
  }

  // Update topic text
  function updateTopic(text: string) {
    if (data.value) {
      data.value.topic = text
    }
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addConcept,
    removeConcept,
    updateConceptText,
    updateConceptPosition,
    addConnection,
    removeConnection,
    updateConnectionLabel,
    updateTopic,
  }
}
