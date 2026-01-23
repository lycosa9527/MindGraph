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
