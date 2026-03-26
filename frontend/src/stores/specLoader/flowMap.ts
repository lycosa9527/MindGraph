/**
 * Flow Map Loader
 * Using Dagre for substep layout, fixed X for step alignment
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_PADDING,
  DEFAULT_STEP_SPACING,
  FLOW_GROUP_GAP,
  FLOW_MAP_PILL_HEIGHT,
  FLOW_MAP_PILL_WIDTH,
  FLOW_MIN_STEP_SPACING,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
  FLOW_TOPIC_TO_STEP_GAP,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import { measureTextWidth } from './textMeasurement'
import type { SpecLoaderResult } from './types'

const FLOW_SUBSTEP_FONT_SIZE = 12
const FLOW_NODE_PADDING_X = 40
/** Topic node: px-6 = 24px each side; fontWeight bold for accurate measurement */
const FLOW_TOPIC_FONT_SIZE = 18
const FLOW_TOPIC_PADDING_X = 48

interface FlowSubstepEntry {
  step: string
  substeps: string[]
}

/**
 * Load flow map spec into diagram nodes and connections
 *
 * @param spec - Flow map spec with steps, substeps, and orientation
 * @returns SpecLoaderResult with nodes and connections
 */
const FLOW_TOPIC_NODE_ID = 'flow-topic'

/**
 * Get centered position for flow map topic in vertical layout.
 * Used when topic text changes to keep it centered over the step column.
 */
export function getFlowTopicCenteredPosition(
  text: string,
  currentY: number
): { x: number; y: number } {
  const stepCenterX = DEFAULT_CENTER_X
  const measuredTextWidth = measureTextWidth(text, FLOW_TOPIC_FONT_SIZE, {
    fontWeight: 'bold',
  })
  const topicEstWidth = Math.max(FLOW_MAP_PILL_WIDTH, measuredTextWidth + FLOW_TOPIC_PADDING_X)
  const x = Math.round(stepCenterX - topicEstWidth / 2)
  const topicCenterX = x + topicEstWidth / 2
  console.log('[FlowMap] getFlowTopicCenteredPosition', {
    text,
    currentY,
    DEFAULT_CENTER_X: stepCenterX,
    measuredTextWidth,
    topicEstWidth,
    x,
    topicCenterX,
    centerOffset: topicCenterX - stepCenterX,
  })
  return { x, y: currentY }
}

/**
 * Post-render layout correction for flow maps.
 * Uses actual DOM-measured node dimensions from Pinia to center-align the topic
 * node with the step column, since node sizes are only known after the first render.
 *
 * Horizontal layout: corrects topic Y so its center matches step nodes' center Y.
 * Vertical layout:   corrects topic X so its center matches step column's center X.
 */
export function recalculateFlowMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return nodes

  const topicNode = nodes.find((n) => n.id === FLOW_TOPIC_NODE_ID)
  if (!topicNode) return nodes

  const topicDims = nodeDimensions[FLOW_TOPIC_NODE_ID]
  if (!topicDims) return nodes

  const stepNodes = nodes.filter((n) => n.type === 'flow')
  if (stepNodes.length === 0) return nodes

  const firstStep = stepNodes[0]
  if (!firstStep.position || !topicNode.position) return nodes

  const firstStepDims = nodeDimensions[firstStep.id]
  if (!firstStepDims) return nodes

  const orientation =
    ((topicNode.data as Record<string, unknown>)?.orientation as string) || 'horizontal'

  const result = nodes.map((n) => ({ ...n }))
  const topicIndex = result.findIndex((n) => n.id === FLOW_TOPIC_NODE_ID)

  if (orientation === 'horizontal') {
    const stepCenterY = firstStep.position.y + firstStepDims.height / 2
    const correctedY = Math.round(stepCenterY - topicDims.height / 2)
    result[topicIndex] = {
      ...result[topicIndex],
      position: { x: topicNode.position.x, y: correctedY },
    }
  } else {
    const stepCenterX = firstStep.position.x + firstStepDims.width / 2
    const correctedX = Math.round(stepCenterX - topicDims.width / 2)
    result[topicIndex] = {
      ...result[topicIndex],
      position: { x: correctedX, y: topicNode.position.y },
    }
  }

  return result
}

export function loadFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  // Steps can be strings or objects with text property
  const rawSteps = (spec.steps as Array<string | { id?: string; text: string }>) || []
  const orientation = (spec.orientation as 'horizontal' | 'vertical') || 'horizontal'
  const substepsData = (spec.substeps as FlowSubstepEntry[]) || []
  const title = (spec.title as string) || ''

  // Normalize steps to objects with text
  const steps = rawSteps.map((step, index) => {
    if (typeof step === 'string') {
      return { id: `flow-step-${index}`, text: step }
    }
    return { id: step.id || `flow-step-${index}`, text: step.text }
  })

  // Build substeps mapping: stepText -> substeps array
  const stepToSubsteps: Record<string, string[]> = {}
  substepsData.forEach((entry) => {
    if (entry && entry.step && Array.isArray(entry.substeps)) {
      stepToSubsteps[entry.step] = entry.substeps
    }
  })

  const isVertical = orientation === 'vertical'
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Unified pill dimensions for flow map (topic, steps, substeps - all same size)
  const pillWidth = FLOW_MAP_PILL_WIDTH
  const pillHeight = FLOW_MAP_PILL_HEIGHT

  if (isVertical) {
    // =========================================================================
    // VERTICAL LAYOUT: Main topic at top, steps stacked vertically below
    // =========================================================================
    const stepX = DEFAULT_CENTER_X - pillWidth / 2 // All steps at same X
    const substepX = stepX + pillWidth + FLOW_SUBSTEP_OFFSET_X

    // Topic centered on step node group (step column only)
    const stepCenterX = stepX + pillWidth / 2
    const measuredTextWidth = measureTextWidth(title, FLOW_TOPIC_FONT_SIZE, {
      fontWeight: 'bold',
    })
    const topicEstWidth = Math.max(FLOW_MAP_PILL_WIDTH, measuredTextWidth + FLOW_TOPIC_PADDING_X)
    const topicX = Math.round(stepCenterX - topicEstWidth / 2)
    const topicY = DEFAULT_PADDING + 40
    const topicCenterX = topicX + topicEstWidth / 2
    console.log('[FlowMap] layout (vertical)', {
      DEFAULT_CENTER_X,
      stepX,
      stepCenterX,
      pillWidth,
      title,
      measuredTextWidth,
      FLOW_TOPIC_PADDING_X,
      topicEstWidth,
      topicX,
      topicY,
      topicCenterX,
      stepColumnLeft: stepX,
      stepColumnRight: stepX + pillWidth,
      centerOffset: topicCenterX - stepCenterX,
    })
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'vertical' },
    })

    // For each step, calculate substep positions
    interface SubstepGroup {
      stepId: string
      stepText: string
      substepIds: string[]
      substepTexts: string[]
      groupHeight: number
      substepPositions: { id: string; y: number }[]
    }

    const substepGroups: SubstepGroup[] = []

    steps.forEach((step, stepIndex) => {
      const stepId = step.id
      const substeps = stepToSubsteps[step.text] || []

      if (substeps.length > 0) {
        // Substeps on the right of step: stacked vertically
        const positions: { id: string; y: number }[] = []

        substeps.forEach((_, i) => {
          const substepId = `flow-substep-${stepIndex}-${i}`
          const y = i * (pillHeight + FLOW_SUBSTEP_SPACING)
          positions.push({ id: substepId, y })
        })

        // Group height = max(step height, substep column height)
        const substepColumnHeight =
          substeps.length * pillHeight + (substeps.length - 1) * FLOW_SUBSTEP_SPACING
        const groupHeight = Math.max(pillHeight, substepColumnHeight)

        substepGroups.push({
          stepId,
          stepText: step.text,
          substepIds: positions.map((p) => p.id),
          substepTexts: substeps,
          groupHeight,
          substepPositions: positions,
        })
      } else {
        // No substeps
        substepGroups.push({
          stepId,
          stepText: step.text,
          substepIds: [],
          substepTexts: [],
          groupHeight: pillHeight,
          substepPositions: [],
        })
      }
    })

    // =========================================================================
    // Position steps vertically: step on left, substeps on right (stacked vertically)
    // Start below the main topic node
    // =========================================================================
    let currentY = DEFAULT_PADDING + 40 + pillHeight + FLOW_TOPIC_TO_STEP_GAP

    substepGroups.forEach((group, groupIndex) => {
      const hasSubsteps = group.substepIds.length > 0
      const groupStartY = currentY

      if (hasSubsteps) {
        // Step on left, vertically centered with substep column
        const substepColumnHeight =
          group.substepPositions.length * pillHeight +
          (group.substepPositions.length - 1) * FLOW_SUBSTEP_SPACING
        const stepY = groupStartY + Math.max(0, (substepColumnHeight - pillHeight) / 2)

        // Create step node with groupIndex for mindmapColors
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: stepY },
          data: { groupIndex: groupIndex },
        })

        // Substeps on the right of step, stacked vertically
        group.substepPositions.forEach((pos, i) => {
          const text = group.substepTexts[i] ?? ''
          nodes.push({
            id: pos.id,
            text,
            type: 'flowSubstep',
            position: { x: substepX, y: groupStartY + pos.y },
            data: { groupIndex: groupIndex },
          })
        })

        currentY += group.groupHeight + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
      } else {
        // No substeps - just place step with groupIndex for mindmapColors
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: groupStartY },
          data: { groupIndex: groupIndex },
        })

        currentY += pillHeight + FLOW_MIN_STEP_SPACING
      }

      // Main flow: straight vertical line (topic -> step1 -> step2 -> step3)
      const stepColor = getMindmapBranchColor(groupIndex).border
      if (groupIndex === 0) {
        connections.push({
          id: `edge-${FLOW_TOPIC_NODE_ID}-${group.stepId}`,
          source: FLOW_TOPIC_NODE_ID,
          target: group.stepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'bottom',
          targetHandle: 'top',
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      } else {
        const prevGroup = substepGroups[groupIndex - 1]
        const prevStepId = prevGroup?.stepId
        if (prevStepId) {
          connections.push({
            id: `edge-${prevStepId}-${group.stepId}`,
            source: prevStepId,
            target: group.stepId,
            sourcePosition: 'bottom',
            targetPosition: 'top',
            sourceHandle: 'bottom',
            targetHandle: 'top',
            edgeType: 'straight',
            style: { strokeColor: stepColor },
          })
        }
      }

      // Substeps: curved branches to the right (mindmap-style)
      if (hasSubsteps) {
        group.substepPositions.forEach((pos, i) => {
          const substepId = group.substepIds[i]
          if (!substepId) {
            return
          }
          connections.push({
            id: `edge-${group.stepId}-${substepId}`,
            source: group.stepId,
            target: substepId,
            sourcePosition: 'right',
            targetPosition: 'left',
            sourceHandle: 'substep-source',
            targetHandle: 'left',
            edgeType: 'curved',
            style: { strokeColor: stepColor },
          })
        })
      }
    })
  } else {
    // =========================================================================
    // HORIZONTAL LAYOUT: Main topic at left, steps left-to-right
    // =========================================================================
    const stepY = DEFAULT_CENTER_Y - pillHeight / 2

    // Main topic node at left, center-aligned with step nodes on Y
    const topicX = DEFAULT_PADDING
    const topicY = DEFAULT_CENTER_Y - pillHeight / 2
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'horizontal' },
    })

    const stepStartX = DEFAULT_PADDING + pillWidth + FLOW_TOPIC_TO_STEP_GAP

    steps.forEach((step, stepIndex) => {
      const stepId = step.id
      const substeps = stepToSubsteps[step.text] || []
      const stepX = stepStartX + stepIndex * DEFAULT_STEP_SPACING

      // Create step node with groupIndex for mindmapColors
      nodes.push({
        id: stepId,
        text: step.text,
        type: 'flow',
        position: { x: stepX, y: stepY },
        data: { groupIndex: stepIndex },
      })

      // Create edge from topic to first step, or previous step (horizontal: left-to-right flow)
      const stepColor = getMindmapBranchColor(stepIndex).border
      if (stepIndex === 0) {
        connections.push({
          id: `edge-${FLOW_TOPIC_NODE_ID}-${stepId}`,
          source: FLOW_TOPIC_NODE_ID,
          target: stepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'right',
          targetHandle: 'left',
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      } else {
        const prevId = steps[stepIndex - 1].id
        connections.push({
          id: `edge-${prevId}-${stepId}`,
          source: prevId,
          target: stepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'right',
          targetHandle: 'left',
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      }

      // Create substep nodes below (center-aligned under the step, straight vertical lines)
      const stepCenterX = stepX + pillWidth / 2

      substeps.forEach((substepText, substepIndex) => {
        const substepId = `flow-substep-${stepIndex}-${substepIndex}`
        const substepY =
          stepY +
          pillHeight +
          FLOW_SUBSTEP_OFFSET_X +
          substepIndex * (pillHeight + FLOW_SUBSTEP_SPACING)
        const estWidth = Math.max(
          FLOW_MAP_PILL_WIDTH,
          measureTextWidth(substepText, FLOW_SUBSTEP_FONT_SIZE) + FLOW_NODE_PADDING_X
        )
        const substepX = stepCenterX - estWidth / 2

        nodes.push({
          id: substepId,
          text: substepText,
          type: 'flowSubstep',
          position: { x: substepX, y: substepY },
          data: { groupIndex: stepIndex },
        })

        connections.push({
          id: `edge-${stepId}-${substepId}`,
          source: stepId,
          target: substepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'center-source',
          targetHandle: 'center-target',
          edgeType: 'tree',
          style: { strokeColor: stepColor },
        })
      })
    })
  }

  return {
    nodes,
    connections,
    metadata: { orientation },
  }
}
