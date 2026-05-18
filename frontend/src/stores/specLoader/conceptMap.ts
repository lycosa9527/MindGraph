/**
 * Concept Map Loader
 * Converts { topic, concepts, relationships } or { topic, concept_units, relationships }
 * to diagram nodes / connections.
 */
import {
  computeDefaultArrowheadForConceptMap,
  getConceptMapNodeCenter,
} from '@/composables/diagrams/conceptMapHandles'
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import {
  minRadiusForNoOverlap,
  pillHalfExtentForOverlap,
  polarToPosition,
} from '@/composables/diagrams/useRadialLayout'
import type { Connection, DiagramNode } from '@/types'
import { normalizeLabel } from '@/utils/cmapLabels'

import type { SpecLoaderResult } from './types'

const CONCEPT_RING_RADIUS = 150
const HIERARCHY_VERTICAL_GAP = 120
const HIERARCHY_HORIZONTAL_GAP = 200
const GRANDCHILD_VERTICAL_SPACING = 90

/** Edge from spec JSON; `label` may be omitted. */
interface ConceptMapRelationshipSpec {
  from: string
  to: string
  label?: string
}

interface ConceptMapRelationship {
  from: string
  to: string
  label: string
}

interface ImportedConceptUnit {
  id: string
  label: string
}

function isConceptMapSpec(spec: Record<string, unknown>): boolean {
  const topicKnown = typeof spec.topic === 'string' && spec.topic.length > 0
  if (!topicKnown || !Array.isArray(spec.relationships)) {
    return false
  }
  const units = spec.concept_units as unknown[] | undefined
  const legacyConcepts = spec.concepts as unknown[] | undefined

  if (Array.isArray(units) && units.length > 0) {
    const unitsValid = units.every(
      (candidate) =>
        candidate !== null &&
        typeof candidate === 'object' &&
        typeof (candidate as { id?: unknown }).id === 'string' &&
        typeof (candidate as { label?: unknown }).label === 'string'
    )
    if (!unitsValid) {
      return false
    }
  }
  if (Array.isArray(legacyConcepts) && legacyConcepts.length > 0) {
    const legacyValid = legacyConcepts.every((value) => typeof value === 'string')
    if (!legacyValid) {
      return false
    }
  }
  return true
}

function computeHierarchicalPositions(
  relationships: ConceptMapRelationship[]
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const halfWidth = DEFAULT_NODE_WIDTH / 2
  const topicY = DEFAULT_PADDING + 40

  positions.set('topic', {
    x: DEFAULT_CENTER_X - halfWidth,
    y: topicY,
  })

  const childrenOf = new Map<string, string[]>()
  for (const relEntry of relationships) {
    const sourceId = relEntry.from
    const targetId = relEntry.to
    if (sourceId && targetId && targetId !== 'topic') {
      const list = childrenOf.get(sourceId) || []
      if (!list.includes(targetId)) list.push(targetId)
      childrenOf.set(sourceId, list)
    }
  }

  const topicChildren = childrenOf.get('topic') || []
  const leftChildren: string[] = []
  const rightChildren: string[] = []
  topicChildren.forEach((idVal, i) => {
    if (i % 2 === 0) leftChildren.push(idVal)
    else rightChildren.push(idVal)
  })

  let leftX = DEFAULT_CENTER_X - HIERARCHY_HORIZONTAL_GAP - halfWidth
  let rightX = DEFAULT_CENTER_X + HIERARCHY_HORIZONTAL_GAP - halfWidth
  const level1Y = topicY + 100 + HIERARCHY_VERTICAL_GAP
  const level2Y = level1Y + HIERARCHY_VERTICAL_GAP
  const leftBranchY = level1Y - 100

  for (const id of leftChildren) {
    positions.set(id, { x: leftX, y: leftBranchY })
    const grandchildren = childrenOf.get(id) || []
    for (let g = 0; g < grandchildren.length; g++) {
      const gc = grandchildren[g]
      if (!gc) continue
      positions.set(gc, {
        x: leftX,
        y: level2Y + g * GRANDCHILD_VERTICAL_SPACING,
      })
    }
    leftX -= HIERARCHY_HORIZONTAL_GAP
  }

  for (const id of rightChildren) {
    positions.set(id, { x: rightX, y: level2Y })
    const grandchildren = childrenOf.get(id) || []
    for (let g = 0; g < grandchildren.length; g++) {
      const gc = grandchildren[g]
      if (!gc) continue
      positions.set(gc, {
        x: rightX,
        y: level2Y + HIERARCHY_VERTICAL_GAP + g * GRANDCHILD_VERTICAL_SPACING,
      })
    }
    rightX += HIERARCHY_HORIZONTAL_GAP
  }

  return positions
}

function polarFallbackRadius(conceptCount: number, halfWidth: number, halfHeight: number): number {
  if (conceptCount <= 0) return CONCEPT_RING_RADIUS
  const pillR = pillHalfExtentForOverlap(halfWidth, halfHeight)
  if (conceptCount === 1) {
    return Math.max(CONCEPT_RING_RADIUS, pillR + 32)
  }
  const noOverlap = minRadiusForNoOverlap(conceptCount, pillR)
  return Math.max(CONCEPT_RING_RADIUS, noOverlap)
}

function dequeueLabelQueue(
  labelQueues: Map<string, string[]>,
  labelKey: string
): string | undefined {
  const queue = labelQueues.get(labelKey)
  if (!queue || queue.length === 0) {
    return undefined
  }
  return queue.shift()
}

export function loadConceptMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  if (!spec || !isConceptMapSpec(spec)) {
    return { nodes, connections }
  }

  const topicText = spec.topic as string
  const topicNorm = normalizeLabel(topicText)
  const rawRelationships =
    Array.isArray(spec.relationships) && spec.relationships.length > 0
      ? (spec.relationships as ConceptMapRelationshipSpec[])
      : []

  const layoutByLabel = spec._layout_positions_by_label as
    | Record<string, { x: number; y: number }>
    | undefined

  function positionFromLayout(displayLabel: string): { x: number; y: number } | undefined {
    if (!layoutByLabel) return undefined
    return layoutByLabel[displayLabel]
  }

  const importedUnitsCandidate = Array.isArray(spec.concept_units)
    ? (spec.concept_units as ImportedConceptUnit[])
    : []

  let branchDisplayLabels: string[] = []

  /** Maps relationship endpoint keys (ids, canonical mind ids, canonical labels). */
  const nameToMindGraphId = new Map<string, string>()

  let resolvedRelationships: ConceptMapRelationship[] = []

  nameToMindGraphId.set(normalizeLabel(topicText), 'topic')
  nameToMindGraphId.set(topicText.trim(), 'topic')
  nameToMindGraphId.set('topic', 'topic')

  if (importedUnitsCandidate.length > 0) {
    const branchUnits = importedUnitsCandidate.filter((u) => u.id !== 'topic')
    branchDisplayLabels = branchUnits.map((u) => normalizeLabel(u.label))

    branchUnits.forEach((unit, index) => {
      const mindId = `concept-${index}`
      nameToMindGraphId.set(unit.id, mindId)
      nameToMindGraphId.set(mindId, mindId)
      nameToMindGraphId.set(normalizeLabel(unit.label), mindId)
    })

    function resolveImportedEndpoint(importedKey: string): string | undefined {
      const directHit = nameToMindGraphId.get(importedKey)
      if (directHit) return directHit
      return nameToMindGraphId.get(normalizeLabel(importedKey.trim()))
    }

    resolvedRelationships = rawRelationships
      .map((rel) => {
        const fromResolved = resolveImportedEndpoint(rel.from)
        const toResolved = resolveImportedEndpoint(rel.to)
        if (!fromResolved || !toResolved) {
          return null
        }
        return {
          from: fromResolved,
          to: toResolved,
          label: rel.label ?? '',
        }
      })
      .filter((rel): rel is ConceptMapRelationship => rel !== null)
  } else {
    const rawConceptLabels = Array.isArray(spec.concepts) ? (spec.concepts as string[]) : []
    const conceptsArr = rawConceptLabels.map((label) => normalizeLabel(label))
    branchDisplayLabels = conceptsArr

    const labelQueues = new Map<string, string[]>()
    conceptsArr.forEach((labelText, index) => {
      const mindId = `concept-${index}`
      nameToMindGraphId.set(mindId, mindId)
      const bucket = labelQueues.get(labelText) ?? []
      bucket.push(mindId)
      labelQueues.set(labelText, bucket)
    })

    resolvedRelationships = rawRelationships
      .map((rel) => {
        const fromNorm = normalizeLabel(rel.from)
        const toNorm = normalizeLabel(rel.to)
        let fromId: string | undefined
        if (rel.from === 'topic') {
          fromId = 'topic'
        } else if (fromNorm === topicNorm) {
          fromId = 'topic'
        } else {
          fromId =
            dequeueLabelQueue(labelQueues, fromNorm) ?? nameToMindGraphId.get(rel.from.trim())
        }

        let toId: string | undefined
        if (rel.to === 'topic') {
          toId = 'topic'
        } else if (toNorm === topicNorm) {
          toId = 'topic'
        } else {
          toId = dequeueLabelQueue(labelQueues, toNorm) ?? nameToMindGraphId.get(rel.to.trim())
        }

        if (!fromId || !toId || fromId === toId) {
          return null
        }
        return {
          from: fromId,
          to: toId,
          label: rel.label ?? '',
        }
      })
      .filter((rel): rel is ConceptMapRelationship => rel !== null)
  }

  const hasHierarchy =
    resolvedRelationships.length > 0 && resolvedRelationships.some((rel) => rel.from === 'topic')

  const hierarchicalPositions =
    hasHierarchy && resolvedRelationships.length > 0
      ? computeHierarchicalPositions(resolvedRelationships)
      : null

  const topicLayout = positionFromLayout(topicText)
  nodes.push({
    id: 'topic',
    text: topicText,
    type: 'topic',
    position: topicLayout
      ? {
          x: topicLayout.x,
          y: topicLayout.y,
        }
      : {
          x: DEFAULT_CENTER_X - DEFAULT_NODE_WIDTH / 2,
          y: DEFAULT_PADDING + 40,
        },
  })

  const conceptCount = branchDisplayLabels.length
  const halfWidth = DEFAULT_NODE_WIDTH / 2
  const halfHeight = 25
  const polarRadius = polarFallbackRadius(conceptCount, halfWidth, halfHeight)

  branchDisplayLabels.forEach((displayLabel, index) => {
    const id = `concept-${index}`
    let position: { x: number; y: number }
    const imported = positionFromLayout(displayLabel)
    const hierPos = hierarchicalPositions?.get(id)
    if (imported) {
      position = {
        x: imported.x,
        y: imported.y,
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
      text: displayLabel,
      type: 'branch',
      position,
    })
  })

  resolvedRelationships.forEach((rel, index) => {
    const sourceId = rel.from
    const targetId = rel.to
    if (!sourceId || !targetId) {
      return
    }
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
  })

  return { nodes, connections }
}
