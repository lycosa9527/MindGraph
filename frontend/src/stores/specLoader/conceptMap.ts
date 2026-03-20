/**
 * Concept Map Loader
 * Converts { topic, concepts, relationships } spec to { nodes, connections }
 * Uses hierarchical layout: topic at top, branches below, children under parents
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { polarToPosition } from '@/composables/diagrams/useRadialLayout'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

const CONCEPT_RING_RADIUS = 150
const HIERARCHY_VERTICAL_GAP = 120
const HIERARCHY_HORIZONTAL_GAP = 200

interface ConceptMapRelationship {
  from: string
  to: string
  label?: string
}

function isConceptMapSpec(spec: Record<string, unknown>): boolean {
  return (
    (typeof spec.topic === 'string' || spec.topic === undefined) && Array.isArray(spec.concepts)
  )
}

function computeHierarchicalPositions(
  topicText: string,
  conceptsArr: string[],
  relationships: ConceptMapRelationship[],
  nameToId: Map<string, string>
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const halfWidth = DEFAULT_NODE_WIDTH / 2
  const topicY = DEFAULT_PADDING + 40

  positions.set('topic', {
    x: DEFAULT_CENTER_X - halfWidth,
    y: topicY,
  })

  const childrenOf = new Map<string, string[]>()
  for (const rel of relationships) {
    const sourceId = nameToId.get(rel.from)
    const targetId = nameToId.get(rel.to)
    if (sourceId && targetId && targetId !== 'topic') {
      const list = childrenOf.get(sourceId) || []
      if (!list.includes(targetId)) list.push(targetId)
      childrenOf.set(sourceId, list)
    }
  }

  const topicChildren = childrenOf.get('topic') || []
  const leftChildren: string[] = []
  const rightChildren: string[] = []
  topicChildren.forEach((id, i) => {
    if (i % 2 === 0) leftChildren.push(id)
    else rightChildren.push(id)
  })

  let leftX = DEFAULT_CENTER_X - HIERARCHY_HORIZONTAL_GAP - halfWidth
  let rightX = DEFAULT_CENTER_X + HIERARCHY_HORIZONTAL_GAP - halfWidth
  const level1Y = topicY + 100 + HIERARCHY_VERTICAL_GAP
  const level2Y = level1Y + HIERARCHY_VERTICAL_GAP
  const leftBranchY = level1Y - 100

  for (const id of leftChildren) {
    positions.set(id, { x: leftX, y: leftBranchY })
    const grandChildren = childrenOf.get(id) || []
    for (let g = 0; g < grandChildren.length; g++) {
      positions.set(grandChildren[g], {
        x: leftX,
        y: level2Y + g * (DEFAULT_NODE_HEIGHT + 40),
      })
    }
    leftX -= HIERARCHY_HORIZONTAL_GAP
  }

  for (const id of rightChildren) {
    positions.set(id, { x: rightX, y: level2Y })
    const grandChildren = childrenOf.get(id) || []
    for (let g = 0; g < grandChildren.length; g++) {
      positions.set(grandChildren[g], {
        x: rightX,
        y: level2Y + HIERARCHY_VERTICAL_GAP + g * (DEFAULT_NODE_HEIGHT + 40),
      })
    }
    rightX += HIERARCHY_HORIZONTAL_GAP
  }

  return positions
}

export function loadConceptMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  if (!spec || !isConceptMapSpec(spec)) {
    return { nodes, connections }
  }

  const topicText = (spec.topic as string) || 'Topic'
  const conceptsArr = spec.concepts as string[]
  const relationships = (spec.relationships as ConceptMapRelationship[]) || []

  const nameToId = new Map<string, string>()
  nameToId.set(topicText, 'topic')

  conceptsArr.forEach((text, index) => {
    nameToId.set(text, `concept-${index}`)
  })

  const hasHierarchy = relationships.some((r) => nameToId.get(r.from) === 'topic')
  const hierarchicalPositions =
    hasHierarchy && relationships.length > 0
      ? computeHierarchicalPositions(topicText, conceptsArr, relationships, nameToId)
      : null

  nodes.push({
    id: 'topic',
    text: topicText,
    type: 'topic',
    position: {
      x: DEFAULT_CENTER_X - DEFAULT_NODE_WIDTH / 2,
      y: DEFAULT_PADDING + 40,
    },
  })

  const conceptCount = conceptsArr.length
  const halfWidth = DEFAULT_NODE_WIDTH / 2
  const halfHeight = DEFAULT_NODE_HEIGHT / 2

  conceptsArr.forEach((text, index) => {
    const id = `concept-${index}`
    let position: { x: number; y: number }
    const hierPos = hierarchicalPositions?.get(id)
    if (hierPos) {
      position = hierPos
    } else {
      position = polarToPosition(
        index,
        conceptCount,
        DEFAULT_CENTER_X,
        DEFAULT_CENTER_Y + 80,
        CONCEPT_RING_RADIUS,
        halfWidth,
        halfHeight
      )
    }
    nodes.push({
      id,
      text,
      type: 'branch',
      position,
    })
  })

  relationships.forEach((rel, index) => {
    const sourceId = nameToId.get(rel.from)
    const targetId = nameToId.get(rel.to)
    if (sourceId && targetId) {
      connections.push({
        id: `conn-${index}`,
        source: sourceId,
        target: targetId,
        label: rel.label || '',
      })
    }
  })

  return { nodes, connections }
}
