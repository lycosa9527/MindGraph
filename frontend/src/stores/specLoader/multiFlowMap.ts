/**
 * Multi-Flow Map Loader
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_SIDE_SPACING,
  DEFAULT_VERTICAL_SPACING,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

/**
 * Recalculate multi-flow map layout from existing nodes
 * Called when nodes are added/deleted to update positions and re-index IDs
 * Preserves node text content
 *
 * @param nodes - Current diagram nodes
 * @returns Recalculated nodes with updated positions and sequential IDs
 */
export function recalculateMultiFlowMapLayout(nodes: DiagramNode[]): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  // Extract event, causes, and effects from current nodes
  const eventNode = nodes.find((n) => n.id === 'event' || n.type === 'topic')
  const causeNodes = nodes
    .filter((n) => n.id?.startsWith('cause-'))
    .sort((a, b) => {
      const aIndex = parseInt(a.id?.replace('cause-', '') || '0', 10)
      const bIndex = parseInt(b.id?.replace('cause-', '') || '0', 10)
      return aIndex - bIndex
    })
  const effectNodes = nodes
    .filter((n) => n.id?.startsWith('effect-'))
    .sort((a, b) => {
      const aIndex = parseInt(a.id?.replace('effect-', '') || '0', 10)
      const bIndex = parseInt(b.id?.replace('effect-', '') || '0', 10)
      return aIndex - bIndex
    })

  const event = eventNode?.text || ''
  const causes = causeNodes.map((n) => n.text)
  const effects = effectNodes.map((n) => n.text)

  // Layout constants
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING + 10 // 70px
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT

  const result: DiagramNode[] = []

  // Event node
  result.push({
    id: 'event',
    text: event,
    type: 'topic',
    position: { x: centerX - nodeWidth / 2, y: centerY - nodeHeight / 2 },
  })

  // Causes - re-index with sequential IDs (cause-0, cause-1, etc.)
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
  causes.forEach((cause, index) => {
    result.push({
      id: `cause-${index}`,
      text: cause,
      type: 'flow',
      position: {
        x: centerX - sideSpacing - nodeWidth / 2,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
  })

  // Effects - re-index with sequential IDs (effect-0, effect-1, etc.)
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
  effects.forEach((effect, index) => {
    result.push({
      id: `effect-${index}`,
      text: effect,
      type: 'flow',
      position: {
        x: centerX + sideSpacing - nodeWidth / 2,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
  })

  return result
}

/**
 * Load multi-flow map spec into diagram nodes and connections
 *
 * @param spec - Multi-flow map spec with event, causes, and effects
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadMultiFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const event = (spec.event as string) || ''
  const causes = (spec.causes as string[]) || []
  const effects = (spec.effects as string[]) || []

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING + 10 // 70px
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Event node
  nodes.push({
    id: 'event',
    text: event,
    type: 'topic',
    position: { x: centerX - nodeWidth / 2, y: centerY - nodeHeight / 2 },
  })

  // Causes
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
  causes.forEach((cause, index) => {
    nodes.push({
      id: `cause-${index}`,
      text: cause,
      type: 'flow',
      position: {
        x: centerX - sideSpacing - nodeWidth / 2,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
    connections.push({
      id: `edge-cause-${index}`,
      source: `cause-${index}`,
      target: 'event',
      sourceHandle: 'right',
      targetHandle: `left-${index}`, // Use specific handle ID matching the cause index
    })
  })

  // Effects
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
  effects.forEach((effect, index) => {
    nodes.push({
      id: `effect-${index}`,
      text: effect,
      type: 'flow',
      position: {
        x: centerX + sideSpacing - nodeWidth / 2,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
    connections.push({
      id: `edge-effect-${index}`,
      source: 'event',
      target: `effect-${index}`,
      sourceHandle: `right-${index}`, // Use specific handle ID matching the effect index
      targetHandle: 'left',
    })
  })

  return { nodes, connections }
}
