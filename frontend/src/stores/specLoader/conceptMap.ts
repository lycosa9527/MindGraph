/**
 * Concept Map Loader
 * Converts { topic, concepts, relationships } spec to { nodes, connections }
 * Uses hierarchical layout: topic at top, branches below, children under parents.
 * Optional `spec._layout_positions_by_label` (e.g. from `.cmap` import) overrides per-label positions.
 */
import {
  computeDefaultArrowheadForConceptMap,
  getConceptMapNodeCenter,
} from '@/composables/diagrams/conceptMapHandles'
import {
  BUBBLE_NODE_HEIGHT,
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  TOPIC_NODE_HEIGHT,
} from '@/composables/diagrams/layoutConfig'
import {
  minRadiusForNoOverlap,
  pillHalfExtentForOverlap,
  polarToPosition,
} from '@/composables/diagrams/useRadialLayout'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

const CONCEPT_RING_RADIUS = 150
const HIERARCHY_VERTICAL_GAP = 120
const HIERARCHY_HORIZONTAL_GAP = 200
const GRANDCHILD_VERTICAL_SPACING = 90

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
        y: level2Y + g * GRANDCHILD_VERTICAL_SPACING,
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
        y: level2Y + HIERARCHY_VERTICAL_GAP + g * GRANDCHILD_VERTICAL_SPACING,
      })
    }
    rightX += HIERARCHY_HORIZONTAL_GAP
  }

  return positions
}

/** Polar fallback ring radius so concepts do not overlap (fixed 150px was too tight for many nodes). */
function polarFallbackRadius(conceptCount: number, halfWidth: number, halfHeight: number): number {
  if (conceptCount <= 0) return CONCEPT_RING_RADIUS
  const pillR = pillHalfExtentForOverlap(halfWidth, halfHeight)
  if (conceptCount === 1) {
    return Math.max(CONCEPT_RING_RADIUS, pillR + 32)
  }
  const noOverlap = minRadiusForNoOverlap(conceptCount, pillR)
  return Math.max(CONCEPT_RING_RADIUS, noOverlap)
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

  const layoutByLabel = spec._layout_positions_by_label as
    | Record<string, { x: number; y: number }>
    | undefined

  function positionFromLayout(label: string): { x: number; y: number } | undefined {
    if (!layoutByLabel) return undefined
    return layoutByLabel[label]
  }

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

  const topicLayout = positionFromLayout(topicText)
  nodes.push({
    id: 'topic',
    text: topicText,
    type: 'topic',
    position: topicLayout
      ? {
          x: topicLayout.x - DEFAULT_NODE_WIDTH / 2,
          y: topicLayout.y - TOPIC_NODE_HEIGHT / 2,
        }
      : {
          x: DEFAULT_CENTER_X - DEFAULT_NODE_WIDTH / 2,
          y: DEFAULT_PADDING + 40,
        },
  })

  const conceptCount = conceptsArr.length
  const halfWidth = DEFAULT_NODE_WIDTH / 2
  const halfHeight = 25
  const polarRadius = polarFallbackRadius(conceptCount, halfWidth, halfHeight)

  conceptsArr.forEach((text, index) => {
    const id = `concept-${index}`
    let position: { x: number; y: number }
    const imported = positionFromLayout(text)
    const hierPos = hierarchicalPositions?.get(id)
    if (imported) {
      position = {
        x: imported.x - DEFAULT_NODE_WIDTH / 2,
        y: imported.y - BUBBLE_NODE_HEIGHT / 2,
      }
    } else if (hierPos) {
      position = hierPos
    } else {
      position = polarToPosition(
        index,
        conceptCount,
        DEFAULT_CENTER_X,
        DEFAULT_CENTER_Y + 80,
        polarRadius,
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
      const sourceNode = nodes.find((n) => n.id === sourceId)
      const targetNode = nodes.find((n) => n.id === targetId)
      const conn: Connection = {
        id: `conn-${index}`,
        source: sourceId,
        target: targetId,
        label: rel.label || '',
      }
      if (sourceNode && targetNode) {
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(
          getConceptMapNodeCenter(sourceNode),
          getConceptMapNodeCenter(targetNode)
        )
      }
      connections.push(conn)
    }
  })

  return { nodes, connections }
}
