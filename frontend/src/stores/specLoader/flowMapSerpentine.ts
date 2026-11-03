/**
 * Horizontal flow maps run left to right, then U-turn.
 * After five steps the next step sits under the last one and the row
 * runs back the other way. The following row turns again.
 */
import {
  FLOW_MAP_ROW_GAP,
  FLOW_MAP_STEPS_PER_ROW,
  FLOW_MIN_STEP_SPACING,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'
import { FLOW_TOPIC_NODE_ID, isFlowMapStepNode, readFlowStepIndex } from '@/utils/flowMapIdentity'

import { resolveFlowMapOrientation } from './flowMapSubsteps'

export type FlowRowDirection = 'ltr' | 'rtl'

export interface FlowStepSlot {
  row: number
  column: number
  direction: FlowRowDirection
}

export interface FlowSerpentineBox {
  footprintWidth: number
  stepWidth: number
  stepHeight: number
  /** Height hanging under the step (substeps), including the gap above them. */
  belowHeight: number
}

export interface FlowSerpentinePlacement extends FlowStepSlot {
  centerX: number
  stepX: number
  stepY: number
}

export interface FlowEdgePorts {
  sourcePosition: 'top' | 'bottom' | 'left' | 'right'
  targetPosition: 'top' | 'bottom' | 'left' | 'right'
  sourceHandle: string
  targetHandle: string
}

const TOPIC_TO_FIRST_STEP: FlowEdgePorts = {
  sourcePosition: 'right',
  targetPosition: 'left',
  sourceHandle: 'right',
  targetHandle: 'left',
}

export function flowStepSlot(index: number, perRow = FLOW_MAP_STEPS_PER_ROW): FlowStepSlot {
  const row = Math.floor(index / perRow)
  const offset = index % perRow
  const direction: FlowRowDirection = row % 2 === 0 ? 'ltr' : 'rtl'
  const column = direction === 'ltr' ? offset : perRow - 1 - offset
  return { row, column, direction }
}

/** Extra height under a step once its substeps are stacked. */
export function flowSubstepStackExtent(heights: readonly number[]): number {
  if (heights.length === 0) return 0
  const stack =
    heights.reduce((sum, height) => sum + height, 0) + FLOW_SUBSTEP_SPACING * (heights.length - 1)
  return FLOW_SUBSTEP_OFFSET_X + stack
}

export function placeFlowSerpentine(
  groups: readonly FlowSerpentineBox[],
  originX: number,
  firstRowCenterY: number,
  columnGap = FLOW_MIN_STEP_SPACING,
  rowGap = FLOW_MAP_ROW_GAP
): FlowSerpentinePlacement[] {
  if (groups.length === 0) return []

  const columnCount = Math.min(FLOW_MAP_STEPS_PER_ROW, groups.length)
  const columnWidth = Array.from({ length: columnCount }, () => 0)
  groups.forEach((group, index) => {
    const slot = flowStepSlot(index)
    const column = Math.min(slot.column, columnCount - 1)
    columnWidth[column] = Math.max(columnWidth[column], group.footprintWidth)
  })

  const centerX: number[] = []
  let cursor = originX
  for (let column = 0; column < columnCount; column += 1) {
    centerX.push(cursor + columnWidth[column] / 2)
    cursor += columnWidth[column] + columnGap
  }

  const placed: FlowSerpentinePlacement[] = []
  let rowCenterY = firstRowCenterY
  let index = 0
  while (index < groups.length) {
    const rowEnd = Math.min(index + FLOW_MAP_STEPS_PER_ROW, groups.length)
    let rowBottom = rowCenterY
    for (let stepIndex = index; stepIndex < rowEnd; stepIndex += 1) {
      const group = groups[stepIndex]
      const slot = flowStepSlot(stepIndex)
      const column = Math.min(slot.column, columnCount - 1)
      const stepY = rowCenterY - group.stepHeight / 2
      rowBottom = Math.max(rowBottom, stepY + group.stepHeight + group.belowHeight)
      placed.push({
        row: slot.row,
        column,
        direction: slot.direction,
        centerX: centerX[column],
        stepX: centerX[column] - group.stepWidth / 2,
        stepY,
      })
    }
    index = rowEnd
    if (index >= groups.length) break
    const nextEnd = Math.min(index + FLOW_MAP_STEPS_PER_ROW, groups.length)
    let nextMaxHeight = 0
    for (let stepIndex = index; stepIndex < nextEnd; stepIndex += 1) {
      nextMaxHeight = Math.max(nextMaxHeight, groups[stepIndex].stepHeight)
    }
    rowCenterY = rowBottom + rowGap + nextMaxHeight / 2
  }
  return placed
}

/** Ports for the arrow that joins two consecutive steps on a horizontal flow. */
export function flowSerpentineStepPorts(sourceIndex: number, targetIndex: number): FlowEdgePorts {
  const from = flowStepSlot(sourceIndex)
  const to = flowStepSlot(targetIndex)
  if (from.row !== to.row) {
    // Step out past the outer side, drop, then come back into the next step.
    if (from.direction === 'ltr') {
      return {
        sourcePosition: 'right',
        targetPosition: 'right',
        sourceHandle: 'right',
        targetHandle: 'right-target',
      }
    }
    return {
      sourcePosition: 'left',
      targetPosition: 'left',
      sourceHandle: 'left-source',
      targetHandle: 'left',
    }
  }
  if (to.direction === 'rtl') {
    return {
      sourcePosition: 'left',
      targetPosition: 'right',
      sourceHandle: 'left-source',
      targetHandle: 'right-target',
    }
  }
  return {
    sourcePosition: 'right',
    targetPosition: 'left',
    sourceHandle: 'right',
    targetHandle: 'left',
  }
}

/**
 * Point main-flow arrows along the serpentine. Substep branches are left alone.
 * Vertical flows stay top-to-bottom.
 */
export function withFlowSerpentineHandles(
  connection: Connection,
  nodes: DiagramNode[]
): Connection {
  const topic = nodes.find((node) => node.id === FLOW_TOPIC_NODE_ID || node.type === 'topic')
  const steps = nodes.filter((node) => isFlowMapStepNode(node))
  const orientation = topic ? resolveFlowMapOrientation(topic, steps) : 'horizontal'
  if (orientation === 'vertical') return connection

  const source = nodes.find((node) => node.id === connection.source)
  const target = nodes.find((node) => node.id === connection.target)
  if (!source || !target || !isFlowMapStepNode(target)) return connection

  if (source.id === FLOW_TOPIC_NODE_ID || source.type === 'topic') {
    return { ...connection, ...TOPIC_TO_FIRST_STEP }
  }
  if (!isFlowMapStepNode(source)) return connection

  const sourceIndex = readFlowStepIndex(source)
  const targetIndex = readFlowStepIndex(target)
  if (sourceIndex < 0 || targetIndex < 0) return connection
  return { ...connection, ...flowSerpentineStepPorts(sourceIndex, targetIndex) }
}
