/**
 * First flow layout uses the pill height. A second line grows the node after
 * that pass, so shift the nodes below it before the DOM is measured.
 */
import {
  FLOW_MAP_PILL_HEIGHT,
  FLOW_MAP_STEPS_PER_ROW,
  FLOW_SUBSTEP_SPACING,
} from '@/composables/diagrams/layoutConfig'
import type { DiagramNode } from '@/types'
import {
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'
import { type FlowPillRole, flowSecondaryExtraHeight } from '@/utils/flowPillBox'

function glossHeight(node: DiagramNode | undefined, role: FlowPillRole): number {
  if (!node) return 0
  return flowSecondaryExtraHeight(node.text ?? '', node.textSecondary, role)
}

function flowRow(step: DiagramNode): number {
  const index = readFlowStepIndex(step)
  if (index < 0) return 0
  return Math.floor(index / FLOW_MAP_STEPS_PER_ROW)
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
    const rowExtra = new Map<number, number>()
    const withinStack = new Map<string, number>()
    for (const step of steps) {
      let accumulated = glossHeight(step, 'step')
      let stack = accumulated
      for (const child of substepsOf(nodes, step.id)) {
        if (accumulated > 0) withinStack.set(child.id, accumulated)
        const childExtra = glossHeight(child, 'substep')
        accumulated += childExtra
        stack += childExtra
      }
      const row = flowRow(step)
      rowExtra.set(row, Math.max(rowExtra.get(row) ?? 0, stack))
    }
    let carried = 0
    const rowShift = new Map<number, number>()
    for (const row of [...rowExtra.keys()].sort((left, right) => left - right)) {
      rowShift.set(row, carried)
      carried += rowExtra.get(row) ?? 0
    }
    for (const step of steps) {
      const down = rowShift.get(flowRow(step)) ?? 0
      if (down > 0) shift.set(step.id, down)
      for (const child of substepsOf(nodes, step.id)) {
        const total = (withinStack.get(child.id) ?? 0) + down
        if (total > 0) shift.set(child.id, total)
      }
    }
  } else {
    let accumulated = glossHeight(topic, 'topic')
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
        inner += glossHeight(child, 'substep')
      }
      const extras = children.map((child) => glossHeight(child, 'substep'))
      const oldColumn = columnHeight(
        children.length,
        extras.map(() => 0)
      )
      const newColumn = columnHeight(children.length, extras)
      const stepExtra = glossHeight(step, 'step')
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
