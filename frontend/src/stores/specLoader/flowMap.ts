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
  FLOW_MAP_TOPIC_WIDTH,
  FLOW_MIN_STEP_SPACING,
  FLOW_NODE_HEIGHT,
  FLOW_NODE_WIDTH,
  FLOW_SUBSTEP_NODE_HEIGHT,
  FLOW_SUBSTEP_NODE_WIDTH,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
  FLOW_TOPIC_TO_STEP_GAP,
  TOPIC_NODE_HEIGHT,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

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

  // Substep node dimensions (from layout config for consistency)
  const substepWidth = FLOW_SUBSTEP_NODE_WIDTH
  const substepHeight = FLOW_SUBSTEP_NODE_HEIGHT

  if (isVertical) {
    // =========================================================================
    // VERTICAL LAYOUT: Main topic at top, steps stacked vertically below
    // =========================================================================
    const stepX = DEFAULT_CENTER_X - FLOW_NODE_WIDTH / 2 // All steps at same X
    const substepX = DEFAULT_CENTER_X + FLOW_NODE_WIDTH / 2 + FLOW_SUBSTEP_OFFSET_X

    // Main topic node at top (left/top of 步骤1)
    const topicX = DEFAULT_CENTER_X - FLOW_MAP_TOPIC_WIDTH / 2
    const topicY = DEFAULT_PADDING + 40
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'vertical' },
    })

    // For each step, calculate substep positions using dagre
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
        // Calculate substep positions manually (simple vertical stack)
        // This is more predictable than dagre for a simple stack
        const positions: { id: string; y: number }[] = []

        substeps.forEach((_, i) => {
          const substepId = `flow-substep-${stepIndex}-${i}`
          // Each substep is positioned with FLOW_SUBSTEP_SPACING between them
          const y = i * (substepHeight + FLOW_SUBSTEP_SPACING)
          positions.push({ id: substepId, y })
        })

        // Group height = all substeps + spacing between them
        const groupHeight =
          substeps.length * substepHeight + (substeps.length - 1) * FLOW_SUBSTEP_SPACING

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
          groupHeight: FLOW_NODE_HEIGHT,
          substepPositions: [],
        })
      }
    })

    // =========================================================================
    // Position steps vertically, centered on their substep groups
    // Start below the main topic node
    // =========================================================================
    const topicHeight = 52 // Approximate topic node height
    let currentY =
      DEFAULT_PADDING + 40 + topicHeight + FLOW_TOPIC_TO_STEP_GAP

    substepGroups.forEach((group, groupIndex) => {
      const hasSubsteps = group.substepIds.length > 0

      if (hasSubsteps) {
        // Step Y is centered on substep group
        const groupCenterY = currentY + group.groupHeight / 2
        const stepY = groupCenterY - FLOW_NODE_HEIGHT / 2

        // Create step node
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: stepY },
        })

        // Create substep nodes (center-aligned in a straight vertical line at substepX)
        // All substeps share the same X coordinate for consistent alignment
        group.substepPositions.forEach((pos, i) => {
          nodes.push({
            id: pos.id,
            text: group.substepTexts[i],
            type: 'flowSubstep',
            position: { x: substepX, y: currentY + pos.y },
          })
        })

        currentY += group.groupHeight + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
      } else {
        // No substeps - just place step
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: currentY },
        })

        currentY += FLOW_NODE_HEIGHT + FLOW_MIN_STEP_SPACING
      }

      // Create edge to previous step or from topic (vertical: top-to-bottom flow)
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
        })
      } else {
        const prevId = substepGroups[groupIndex - 1].stepId
        connections.push({
          id: `edge-${prevId}-${group.stepId}`,
          source: prevId,
          target: group.stepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'bottom',
          targetHandle: 'top',
          edgeType: 'straight',
        })
      }

      // Create edges to substeps
      group.substepIds.forEach((substepId) => {
        connections.push({
          id: `edge-${group.stepId}-${substepId}`,
          source: group.stepId,
          target: substepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'substep-source',
          edgeType: 'horizontalStep',
        })
      })
    })
  } else {
    // =========================================================================
    // HORIZONTAL LAYOUT: Main topic at left, steps left-to-right
    // =========================================================================
    const stepY = DEFAULT_CENTER_Y - FLOW_NODE_HEIGHT / 2

    // Main topic node at left, center-aligned with step nodes on Y
    const topicX = DEFAULT_PADDING
    const topicY = DEFAULT_CENTER_Y - TOPIC_NODE_HEIGHT / 2
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'horizontal' },
    })

    const stepStartX = DEFAULT_PADDING + FLOW_MAP_TOPIC_WIDTH + FLOW_TOPIC_TO_STEP_GAP

    steps.forEach((step, stepIndex) => {
      const stepId = step.id
      const substeps = stepToSubsteps[step.text] || []
      const stepX = stepStartX + stepIndex * DEFAULT_STEP_SPACING

      // Create step node
      nodes.push({
        id: stepId,
        text: step.text,
        type: 'flow',
        position: { x: stepX, y: stepY },
      })

      // Create edge from topic to first step, or previous step (horizontal: left-to-right flow)
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
        })
      }

      // Create substep nodes below (center-aligned under the step, in a straight vertical line)
      // All substeps share the same X center as the parent step
      const stepCenterX = stepX + FLOW_NODE_WIDTH / 2
      const substepCenterAlignedX = stepCenterX - substepWidth / 2

      substeps.forEach((substepText, substepIndex) => {
        const substepId = `flow-substep-${stepIndex}-${substepIndex}`
        const substepY =
          stepY +
          FLOW_NODE_HEIGHT +
          FLOW_SUBSTEP_OFFSET_X +
          substepIndex * (substepHeight + FLOW_SUBSTEP_SPACING)

        nodes.push({
          id: substepId,
          text: substepText,
          type: 'flowSubstep',
          position: { x: substepCenterAlignedX, y: substepY },
        })

        connections.push({
          id: `edge-${stepId}-${substepId}`,
          source: stepId,
          target: substepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'bottom',
          targetHandle: 'top-target',
          edgeType: 'step',
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
