/**
 * Flow Map Loader
 * Using Dagre for substep layout, fixed X for step alignment
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_PADDING,
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
const FLOW_STEP_FONT_SIZE = 13
const FLOW_NODE_PADDING_X = 40
/** Topic node: px-6 = 24px each side; fontWeight bold for accurate measurement */
const FLOW_TOPIC_FONT_SIZE = 18
const FLOW_TOPIC_PADDING_X = 48
const FLOW_MAX_TEXT_WIDTH = 250
const FLOW_TOPIC_MAX_TEXT_WIDTH = 300
const FLOW_SUBSTEP_MAX_TEXT_WIDTH = 180
const FLOW_BALANCE_PADDING = 5

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

function estimateFlowRenderedWidth(
  text: string,
  fontSize: number,
  maxTextWidth: number,
  paddingX: number,
  fontWeight: string = 'normal'
): number {
  const trimmed = (text || '').trim()
  if (!trimmed || typeof document === 'undefined') return FLOW_MAP_PILL_WIDTH

  const singleLineWidth = measureTextWidth(trimmed, fontSize, { fontWeight })

  let effectiveTextWidth: number
  if (singleLineWidth <= maxTextWidth) {
    effectiveTextWidth = singleLineWidth
  } else {
    const numLines = Math.ceil(singleLineWidth / maxTextWidth)
    const balancedWidth = Math.ceil(singleLineWidth / numLines) + FLOW_BALANCE_PADDING
    effectiveTextWidth = Math.min(balancedWidth, maxTextWidth)
  }

  return Math.max(FLOW_MAP_PILL_WIDTH, effectiveTextWidth + paddingX)
}

function getEffectiveFlowWidth(
  nodeId: string,
  text: string,
  fontSize: number,
  maxTextWidth: number,
  paddingX: number,
  nodeDimensions: Record<string, { width: number; height: number }>,
  fontWeight: string = 'normal'
): number {
  const measured = nodeDimensions[nodeId]?.width
  const estimated = estimateFlowRenderedWidth(text, fontSize, maxTextWidth, paddingX, fontWeight)
  return measured !== undefined ? Math.max(measured, estimated) : estimated
}

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
  return { x, y: currentY }
}

/**
 * Post-render layout correction for flow maps.
 * Uses actual DOM-measured node dimensions from Pinia to:
 * - Horizontal layout: correct topic Y so its center matches step nodes' center Y.
 * - Vertical layout: restack step (and substep) nodes using measured heights to
 *   prevent overlaps when text wraps, then correct topic X to stay centered.
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
    const orderedSteps = result
      .filter((n) => n.type === 'flow')
      .sort((a, b) => {
        const ga = ((a.data as Record<string, unknown>)?.groupIndex as number) ?? 0
        const gb = ((b.data as Record<string, unknown>)?.groupIndex as number) ?? 0
        return ga - gb
      })
    const substepNodesH = result.filter((n) => n.type === 'flowSubstep')

    const groupInfos = orderedSteps.map((stepNode) => {
      const groupIdx = ((stepNode.data as Record<string, unknown>)?.groupIndex as number) ?? 0
      const stepW = getEffectiveFlowWidth(
        stepNode.id,
        stepNode.text ?? '',
        FLOW_STEP_FONT_SIZE,
        FLOW_MAX_TEXT_WIDTH,
        FLOW_NODE_PADDING_X,
        nodeDimensions
      )
      const groupSubsteps = substepNodesH.filter((n) =>
        n.id.startsWith(`flow-substep-${groupIdx}-`)
      )
      const maxSubW = groupSubsteps.reduce((maxW, sub) => {
        const subW = getEffectiveFlowWidth(
          sub.id,
          sub.text ?? '',
          FLOW_SUBSTEP_FONT_SIZE,
          FLOW_SUBSTEP_MAX_TEXT_WIDTH,
          FLOW_NODE_PADDING_X,
          nodeDimensions
        )
        return Math.max(maxW, subW)
      }, 0)

      return { stepNode, stepW, groupSubsteps, footprintWidth: Math.max(stepW, maxSubW) }
    })

    const topicEstW = estimateFlowRenderedWidth(
      topicNode.text ?? '',
      FLOW_TOPIC_FONT_SIZE,
      FLOW_TOPIC_MAX_TEXT_WIDTH,
      FLOW_TOPIC_PADDING_X,
      'bold'
    )
    const effectiveTopicW = Math.max(topicDims.width, topicEstW)

    const referenceCenterY = DEFAULT_CENTER_Y
    let curX = topicNode.position.x + effectiveTopicW + FLOW_TOPIC_TO_STEP_GAP
    groupInfos.forEach((group) => {
      const centerX = curX + group.footprintWidth / 2
      const stepX = Math.round(centerX - group.stepW / 2)
      const stepH = nodeDimensions[group.stepNode.id]?.height ?? FLOW_MAP_PILL_HEIGHT
      const stepY = Math.round(referenceCenterY - stepH / 2)
      const stepIdx = result.findIndex((n) => n.id === group.stepNode.id)
      result[stepIdx] = {
        ...result[stepIdx],
        position: { x: stepX, y: stepY },
      }

      const sortedSubsteps = [...group.groupSubsteps].sort((a, b) => {
        const aIdx = parseInt(a.id.split('-').pop() ?? '0')
        const bIdx = parseInt(b.id.split('-').pop() ?? '0')
        return aIdx - bIdx
      })
      let subY = stepY + stepH + FLOW_SUBSTEP_OFFSET_X
      sortedSubsteps.forEach((sub) => {
        const subW = getEffectiveFlowWidth(
          sub.id,
          sub.text ?? '',
          FLOW_SUBSTEP_FONT_SIZE,
          FLOW_SUBSTEP_MAX_TEXT_WIDTH,
          FLOW_NODE_PADDING_X,
          nodeDimensions
        )
        const subX = Math.round(centerX - subW / 2)
        const subH = nodeDimensions[sub.id]?.height ?? FLOW_MAP_PILL_HEIGHT
        const subIdx = result.findIndex((n) => n.id === sub.id)
        result[subIdx] = {
          ...result[subIdx],
          position: { x: subX, y: subY },
        }
        subY += subH + FLOW_SUBSTEP_SPACING
      })

      curX += group.footprintWidth + FLOW_MIN_STEP_SPACING
    })

    const firstOrderedStep = orderedSteps[0]
    const firstOrderedStepDims = firstOrderedStep ? nodeDimensions[firstOrderedStep.id] : undefined
    if (firstOrderedStep && firstOrderedStepDims) {
      const firstStepResultNode = result.find((n) => n.id === firstOrderedStep.id)
      const stepPos = firstStepResultNode?.position
      if (stepPos) {
        const stepCenterY = stepPos.y + firstOrderedStepDims.height / 2
        const correctedY = Math.round(stepCenterY - topicDims.height / 2)
        result[topicIndex] = {
          ...result[topicIndex],
          position: { x: topicNode.position.x, y: correctedY },
        }
      }
    }
  } else {
    // Restack step groups from top to bottom using measured heights so that
    // text-wrapped (taller) nodes don't overlap the ones beneath them.
    const substepNodes = result.filter((n) => n.type === 'flowSubstep')
    const orderedSteps = result
      .filter((n) => n.type === 'flow')
      .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))

    let currentY = orderedSteps[0]?.position?.y ?? firstStep.position.y

    orderedSteps.forEach((stepNode, stepOrder) => {
      const stepDims = nodeDimensions[stepNode.id]
      const stepH = stepDims?.height ?? FLOW_MAP_PILL_HEIGHT

      // Substep IDs are flow-substep-{stepIndex}-{i}; stepIndex == position in
      // the original sorted order so we can match them without needing connections.
      const groupSubsteps = substepNodes
        .filter((n) => n.id.startsWith(`flow-substep-${stepOrder}-`))
        .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))

      if (groupSubsteps.length > 0) {
        let substepColumnH = 0
        groupSubsteps.forEach((sub, i) => {
          const subH = nodeDimensions[sub.id]?.height ?? FLOW_MAP_PILL_HEIGHT
          substepColumnH += subH + (i > 0 ? FLOW_SUBSTEP_SPACING : 0)
        })

        const groupH = Math.max(stepH, substepColumnH)
        const stepY = Math.round(currentY + Math.max(0, (substepColumnH - stepH) / 2))
        const stepResultIdx = result.findIndex((n) => n.id === stepNode.id)
        const stepPrevPos = result[stepResultIdx].position
        result[stepResultIdx] = {
          ...result[stepResultIdx],
          position: { x: stepPrevPos?.x ?? 0, y: stepY },
        }

        let subY = Math.round(currentY + Math.max(0, (stepH - substepColumnH) / 2))
        groupSubsteps.forEach((sub) => {
          const subH = nodeDimensions[sub.id]?.height ?? FLOW_MAP_PILL_HEIGHT
          const subResultIdx = result.findIndex((n) => n.id === sub.id)
          const subPrevPos = result[subResultIdx].position
          result[subResultIdx] = {
            ...result[subResultIdx],
            position: { x: subPrevPos?.x ?? 0, y: subY },
          }
          subY += subH + FLOW_SUBSTEP_SPACING
        })

        currentY += groupH + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
      } else {
        const stepResultIdx = result.findIndex((n) => n.id === stepNode.id)
        const loneStepPrevPos = result[stepResultIdx].position
        result[stepResultIdx] = {
          ...result[stepResultIdx],
          position: { x: loneStepPrevPos?.x ?? 0, y: currentY },
        }
        currentY += stepH + FLOW_MIN_STEP_SPACING
      }
    })

    orderedSteps.forEach((stepNode, stepOrder) => {
      const stepResultNode = result.find((n) => n.id === stepNode.id)
      if (!stepResultNode) return
      const stepW = getEffectiveFlowWidth(
        stepNode.id,
        stepNode.text ?? '',
        FLOW_STEP_FONT_SIZE,
        FLOW_MAX_TEXT_WIDTH,
        FLOW_NODE_PADDING_X,
        nodeDimensions
      )
      const substepBaseX = (stepResultNode.position?.x ?? 0) + stepW + FLOW_SUBSTEP_OFFSET_X

      const groupSubs = substepNodes.filter((n) => n.id.startsWith(`flow-substep-${stepOrder}-`))
      groupSubs.forEach((sub) => {
        const subResultIdx = result.findIndex((n) => n.id === sub.id)
        const subHorizPrevPos = result[subResultIdx].position
        result[subResultIdx] = {
          ...result[subResultIdx],
          position: { x: substepBaseX, y: subHorizPrevPos?.y ?? 0 },
        }
      })
    })

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
    // Each step-substep group is sized independently to prevent overlaps
    // =========================================================================
    const stepY = DEFAULT_CENTER_Y - pillHeight / 2

    // Measure topic node width (adaptive: max-content with minWidth 120px)
    const topicTextW = measureTextWidth(title, FLOW_TOPIC_FONT_SIZE, { fontWeight: 'bold' })
    const topicEstWidth = Math.max(pillWidth, topicTextW + FLOW_TOPIC_PADDING_X)
    const topicX = DEFAULT_PADDING
    const topicY = DEFAULT_CENTER_Y - pillHeight / 2
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'horizontal' },
    })

    // Phase 1: Calculate each step-substep group's footprint width
    interface HGroupInfo {
      stepId: string
      stepText: string
      substepEntries: { text: string; estimatedWidth: number }[]
      stepEstimatedWidth: number
      footprintWidth: number
    }

    const hGroups: HGroupInfo[] = steps.map((step) => {
      const subs = stepToSubsteps[step.text] || []
      const stepTextW = measureTextWidth(step.text, FLOW_STEP_FONT_SIZE)
      const stepEstW = Math.max(pillWidth, stepTextW + FLOW_NODE_PADDING_X)

      const substepEntries = subs.map((txt) => {
        const w = measureTextWidth(txt, FLOW_SUBSTEP_FONT_SIZE)
        return {
          text: txt,
          estimatedWidth: Math.max(FLOW_MAP_PILL_WIDTH, w + FLOW_NODE_PADDING_X),
        }
      })

      const maxSubW = substepEntries.reduce((m, s) => Math.max(m, s.estimatedWidth), 0)
      return {
        stepId: step.id,
        stepText: step.text,
        substepEntries,
        stepEstimatedWidth: stepEstW,
        footprintWidth: Math.max(stepEstW, maxSubW),
      }
    })

    // Phase 2: Accumulate X positions with FLOW_MIN_STEP_SPACING gap between groups
    const stepStartX = DEFAULT_PADDING + topicEstWidth + FLOW_TOPIC_TO_STEP_GAP
    const hPositions: { groupCenterX: number; stepX: number }[] = []
    let curX = stepStartX

    hGroups.forEach((g) => {
      const centerX = curX + g.footprintWidth / 2
      hPositions.push({
        groupCenterX: centerX,
        stepX: centerX - g.stepEstimatedWidth / 2,
      })
      curX += g.footprintWidth + FLOW_MIN_STEP_SPACING
    })

    // Phase 3: Place step nodes, substep nodes, and connections
    hGroups.forEach((group, stepIndex) => {
      const { groupCenterX, stepX } = hPositions[stepIndex]

      nodes.push({
        id: group.stepId,
        text: group.stepText,
        type: 'flow',
        position: { x: stepX, y: stepY },
        data: { groupIndex: stepIndex },
      })

      const stepColor = getMindmapBranchColor(stepIndex).border
      if (stepIndex === 0) {
        connections.push({
          id: `edge-${FLOW_TOPIC_NODE_ID}-${group.stepId}`,
          source: FLOW_TOPIC_NODE_ID,
          target: group.stepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'right',
          targetHandle: 'left',
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      } else {
        const prevId = hGroups[stepIndex - 1].stepId
        connections.push({
          id: `edge-${prevId}-${group.stepId}`,
          source: prevId,
          target: group.stepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'right',
          targetHandle: 'left',
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      }

      group.substepEntries.forEach((substep, substepIndex) => {
        const substepId = `flow-substep-${stepIndex}-${substepIndex}`
        const substepY =
          stepY +
          pillHeight +
          FLOW_SUBSTEP_OFFSET_X +
          substepIndex * (pillHeight + FLOW_SUBSTEP_SPACING)
        const substepX = groupCenterX - substep.estimatedWidth / 2

        nodes.push({
          id: substepId,
          text: substep.text,
          type: 'flowSubstep',
          position: { x: substepX, y: substepY },
          data: { groupIndex: stepIndex },
        })

        connections.push({
          id: `edge-${group.stepId}-${substepId}`,
          source: group.stepId,
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
