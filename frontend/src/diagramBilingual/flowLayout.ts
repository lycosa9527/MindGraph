/**
 * First flow layout uses the pill height. A second line grows the node after
 * that pass, so shift the nodes below it before the DOM is measured.
 */
import { FLOW_MAP_PILL_HEIGHT, FLOW_SUBSTEP_SPACING } from '@/composables/diagrams/layoutConfig'
import {
  FLOW_STEP_FONT_SIZE,
  FLOW_SUBSTEP_FONT_SIZE,
  FLOW_TOPIC_FONT_SIZE,
} from '@/stores/specLoader/flowMap'
import type { DiagramNode } from '@/types'
import {
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  readFlowParentStepId,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'

import { secondaryLineBoxHeight } from './measure'

function glossHeight(node: DiagramNode | undefined, fontSize: number): number {
  const gloss = (node?.textSecondary ?? '').trim()
  if (!gloss) return 0
  return secondaryLineBoxHeight(fontSize)
}

function substepsOf(nodes: readonly DiagramNode[], stepId: string): DiagramNode[] {
  return nodes
    .filter((node) => isFlowMapSubstepNode(node) && readFlowParentStepId(node) === stepId)
    .sort(
      (left, right) =>
        readFlowSubstepIndex(left) - readFlowSubstepIndex(right) ||
        (left.position?.y ?? 0) - (right.position?.y ?? 0)
    )
}

function columnHeight(count: number, extras: readonly number[]): number {
  if (count === 0) return 0
  let height = 0
  for (let index = 0; index < count; index += 1) {
    height += FLOW_MAP_PILL_HEIGHT + (extras[index] ?? 0)
    if (index > 0) height += FLOW_SUBSTEP_SPACING
  }
  return height
}

export function offsetFlowLayoutForSecondary(nodes: DiagramNode[]): DiagramNode[] {
  const topic = nodes.find((node) => node.id === 'flow-topic' || node.type === 'topic')
  const vertical = (topic?.data as { orientation?: string } | undefined)?.orientation === 'vertical'
  const steps = nodes.filter((node) => isFlowMapStepNode(node))
  const shift = new Map<string, number>()

  if (!vertical) {
    for (const step of steps) {
      let accumulated = glossHeight(step, FLOW_STEP_FONT_SIZE)
      for (const child of substepsOf(nodes, step.id)) {
        if (accumulated > 0) shift.set(child.id, accumulated)
        accumulated += glossHeight(child, FLOW_SUBSTEP_FONT_SIZE)
      }
    }
  } else {
    let accumulated = glossHeight(topic, FLOW_TOPIC_FONT_SIZE)
    const ordered = [...steps].sort(
      (left, right) => (left.position?.y ?? 0) - (right.position?.y ?? 0)
    )
    for (const step of ordered) {
      if (accumulated > 0) shift.set(step.id, accumulated)
      const children = substepsOf(nodes, step.id)
      let inner = 0
      for (const child of children) {
        const moved = accumulated + inner
        if (moved > 0) shift.set(child.id, moved)
        inner += glossHeight(child, FLOW_SUBSTEP_FONT_SIZE)
      }
      const extras = children.map((child) => glossHeight(child, FLOW_SUBSTEP_FONT_SIZE))
      const oldColumn = columnHeight(
        children.length,
        extras.map(() => 0)
      )
      const newColumn = columnHeight(children.length, extras)
      const stepExtra = glossHeight(step, FLOW_STEP_FONT_SIZE)
      const oldGroup =
        children.length === 0 ? FLOW_MAP_PILL_HEIGHT : Math.max(FLOW_MAP_PILL_HEIGHT, oldColumn)
      const newGroup =
        children.length === 0
          ? FLOW_MAP_PILL_HEIGHT + stepExtra
          : Math.max(FLOW_MAP_PILL_HEIGHT + stepExtra, newColumn)
      accumulated += newGroup - oldGroup
    }
  }

  if (shift.size === 0) return nodes
  return nodes.map((node) => {
    const delta = shift.get(node.id)
    if (!delta || !node.position) return node
    return { ...node, position: { ...node.position, y: node.position.y + delta } }
  })
}
