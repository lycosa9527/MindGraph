/**
 * Flow Map Loader
 * Horizontal steps run left to right, then U-turn onto the next row after
 * five steps. Vertical steps stay in one column. Substeps stack beside or
 * under their step. Positions use the browser's border box once it exists,
 * and a clamped text estimate until then.
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
import type { Connection, DiagramNode, MindMapAdornmentsByPath } from '@/types'
import {
  FLOW_MAP_UID_DATA_KEY,
  FLOW_TOPIC_NODE_ID,
  stampFlowMapStepData,
  stampFlowMapSubstepData,
  takeFlowMapStableId,
} from '@/utils/flowMapIdentity'
import {
  FLOW_TOPIC_FONT_SIZE,
  type FlowPillFont,
  type FlowPillRole,
  flowSecondaryExtraHeight,
  measureFlowRolePill,
} from '@/utils/flowPillBox'
import { measuredBoxExtent } from '@/utils/measuredBoxExtent'
import { textWithIconAdornment } from '@/utils/mindMapAdornments'
import { thinkingMapFamilyLine } from '@/utils/thinkingMapChrome'

import {
  flowSerpentineStepPorts,
  flowSubstepStackExtent,
  placeFlowSerpentine,
} from './flowMapSerpentine'
import {
  type FlowSubstepEntry,
  orderFlowStepNodes,
  resolveFlowMapOrientation,
  resolveFlowSubstepsForSteps,
  substepsForFlowStep,
} from './flowMapSubsteps'
import { learningSheetLayoutSecondary, learningSheetLayoutText } from './mindMapLearningSheet'
import type { SpecLoaderResult } from './types'

function flowNodeTypography(node: DiagramNode | undefined): FlowPillFont {
  const weight = node?.style?.fontWeight
  return {
    fontSize: typeof node?.style?.fontSize === 'number' ? node.style.fontSize : undefined,
    fontWeight: typeof weight === 'string' ? weight : undefined,
    fontFamily: node?.style?.fontFamily,
  }
}

function estimateFlowPill(text: string, role: FlowPillRole, font: FlowPillFont = {}) {
  return measureFlowRolePill(text, role, font)
}

function flowBoxHeight(
  node: DiagramNode,
  role: FlowPillRole,
  measured: number | undefined,
  label = learningSheetLayoutText(node)
): number {
  const typ = flowNodeTypography(node)
  const box = estimateFlowPill(label, role, typ)
  const estimated =
    box.boxHeight + flowSecondaryExtraHeight(label, learningSheetLayoutSecondary(node), role, typ)
  return measuredBoxExtent(measured, estimated, FLOW_MAP_PILL_HEIGHT)
}

/** Width used to center a pill. The estimate is a stand-in until the border box exists. */
function flowCenteringWidth(measured: number | undefined, estimated: number): number {
  return measuredBoxExtent(measured, estimated, FLOW_MAP_PILL_WIDTH)
}

function effectiveFlowWidth(
  nodeId: string,
  text: string,
  role: FlowPillRole,
  font: FlowPillFont,
  nodeDimensions: Record<string, { width: number; height: number }>
): number {
  return flowCenteringWidth(
    nodeDimensions[nodeId]?.width,
    estimateFlowPill(text, role, font).boxWidth
  )
}

/**
 * Get centered position for flow map topic in vertical layout.
 * Used when topic text changes to keep it centered over the step column.
 */
export function getFlowTopicCenteredPosition(
  text: string,
  currentY: number,
  style?: DiagramNode['style']
): { x: number; y: number } {
  const stepCenterX = DEFAULT_CENTER_X
  const fs = typeof style?.fontSize === 'number' ? style.fontSize : FLOW_TOPIC_FONT_SIZE
  const fw = (style?.fontWeight as string | undefined) ?? 'bold'
  const fontFamily = style?.fontFamily
  const topicEstWidth = estimateFlowPill(text, 'topic', {
    fontSize: fs,
    fontWeight: fw,
    fontFamily,
  }).boxWidth
  const x = Math.round(stepCenterX - topicEstWidth / 2)
  return { x, y: currentY }
}

/**
 * Live layout for flow maps. Uses DOM-measured node dimensions from Pinia,
 * falling back to the text estimate for a node not measured yet, to:
 * - Horizontal layout: correct topic Y so its center matches step nodes' center Y.
 * - Vertical layout: restack step (and substep) nodes using measured heights to
 *   prevent overlaps when text wraps, then correct topic X to stay centered.
 */
export function recalculateFlowMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {},
  adornments: MindMapAdornmentsByPath = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return nodes
  const flowLabel = (node: DiagramNode): string =>
    textWithIconAdornment(learningSheetLayoutText(node), adornments[node.id])

  const topicNode = nodes.find((n) => n.id === FLOW_TOPIC_NODE_ID)
  if (!topicNode) return nodes

  const topicDims = nodeDimensions[FLOW_TOPIC_NODE_ID]

  const stepNodes = orderFlowStepNodes(nodes)
  if (stepNodes.length === 0) return nodes

  const firstStep = stepNodes[0]
  if (!firstStep.position || !topicNode.position) return nodes

  const orientation = resolveFlowMapOrientation(topicNode, stepNodes)

  const result = nodes.map((n) => ({ ...n }))
  const topicIndex = result.findIndex((n) => n.id === FLOW_TOPIC_NODE_ID)

  if (orientation === 'horizontal') {
    const orderedSteps = orderFlowStepNodes(result)
    const substepNodesH = result.filter((n) => n.type === 'flowSubstep')

    const groupInfos = orderedSteps.map((stepNode) => {
      const stepTyp = flowNodeTypography(stepNode)
      const stepW = effectiveFlowWidth(
        stepNode.id,
        flowLabel(stepNode),
        'step',
        stepTyp,
        nodeDimensions
      )
      const groupSubsteps = substepsForFlowStep(substepNodesH, stepNode)
      const maxSubW = groupSubsteps.reduce((maxW, sub) => {
        const subTyp = flowNodeTypography(sub)
        const subW = effectiveFlowWidth(sub.id, flowLabel(sub), 'substep', subTyp, nodeDimensions)
        return Math.max(maxW, subW)
      }, 0)

      return { stepNode, stepW, groupSubsteps, footprintWidth: Math.max(stepW, maxSubW) }
    })

    const topicTyp = flowNodeTypography(topicNode)
    const topicEstW = estimateFlowPill(flowLabel(topicNode), 'topic', topicTyp).boxWidth
    const effectiveTopicW = flowCenteringWidth(topicDims?.width, topicEstW)

    const boxes = groupInfos.map((group) => {
      const stepH = flowBoxHeight(
        group.stepNode,
        'step',
        nodeDimensions[group.stepNode.id]?.height,
        flowLabel(group.stepNode)
      )
      const subHeights = group.groupSubsteps.map((sub) =>
        flowBoxHeight(sub, 'substep', nodeDimensions[sub.id]?.height, flowLabel(sub))
      )
      return {
        footprintWidth: group.footprintWidth,
        stepWidth: group.stepW,
        stepHeight: stepH,
        belowHeight: flowSubstepStackExtent(subHeights),
      }
    })
    const placed = placeFlowSerpentine(
      boxes,
      topicNode.position.x + effectiveTopicW + FLOW_TOPIC_TO_STEP_GAP,
      DEFAULT_CENTER_Y
    )
    groupInfos.forEach((group, index) => {
      const place = placed[index]
      const stepH = boxes[index].stepHeight
      const stepX = Math.round(place.stepX)
      const stepY = Math.round(place.stepY)
      const stepIdx = result.findIndex((n) => n.id === group.stepNode.id)
      result[stepIdx] = {
        ...result[stepIdx],
        position: { x: stepX, y: stepY },
      }

      let subY = stepY + stepH + FLOW_SUBSTEP_OFFSET_X
      group.groupSubsteps.forEach((sub) => {
        const subTyp = flowNodeTypography(sub)
        const subW = effectiveFlowWidth(sub.id, flowLabel(sub), 'substep', subTyp, nodeDimensions)
        const subX = Math.round(place.centerX - subW / 2)
        const subH = flowBoxHeight(sub, 'substep', nodeDimensions[sub.id]?.height, flowLabel(sub))
        const subIdx = result.findIndex((n) => n.id === sub.id)
        result[subIdx] = {
          ...result[subIdx],
          position: { x: subX, y: subY },
        }
        subY += subH + FLOW_SUBSTEP_SPACING
      })
    })

    const firstOrderedStep = orderedSteps[0]
    if (firstOrderedStep) {
      const firstStepResultNode = result.find((n) => n.id === firstOrderedStep.id)
      const stepPos = firstStepResultNode?.position
      if (stepPos) {
        const stepH = flowBoxHeight(
          firstOrderedStep,
          'step',
          nodeDimensions[firstOrderedStep.id]?.height,
          flowLabel(firstOrderedStep)
        )
        const topicH = flowBoxHeight(topicNode, 'topic', topicDims?.height, flowLabel(topicNode))
        const stepCenterY = stepPos.y + stepH / 2
        const correctedY = Math.round(stepCenterY - topicH / 2)
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
    const orderedSteps = orderFlowStepNodes(result)

    let currentY = orderedSteps[0]?.position?.y ?? firstStep.position.y

    orderedSteps.forEach((stepNode) => {
      const stepDims = nodeDimensions[stepNode.id]
      const stepH = flowBoxHeight(stepNode, 'step', stepDims?.height, flowLabel(stepNode))

      const groupSubsteps = substepsForFlowStep(substepNodes, stepNode)

      if (groupSubsteps.length > 0) {
        let substepColumnH = 0
        groupSubsteps.forEach((sub, i) => {
          const subH = flowBoxHeight(sub, 'substep', nodeDimensions[sub.id]?.height, flowLabel(sub))
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
          const subH = flowBoxHeight(sub, 'substep', nodeDimensions[sub.id]?.height, flowLabel(sub))
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

    orderedSteps.forEach((stepNode) => {
      const stepResultNode = result.find((n) => n.id === stepNode.id)
      if (!stepResultNode) return
      const stepTyp = flowNodeTypography(stepNode)
      const stepW = effectiveFlowWidth(
        stepNode.id,
        flowLabel(stepNode),
        'step',
        stepTyp,
        nodeDimensions
      )
      const substepBaseX = (stepResultNode.position?.x ?? 0) + stepW + FLOW_SUBSTEP_OFFSET_X

      const groupSubs = substepsForFlowStep(substepNodes, stepNode)
      groupSubs.forEach((sub) => {
        const subResultIdx = result.findIndex((n) => n.id === sub.id)
        const subHorizPrevPos = result[subResultIdx].position
        result[subResultIdx] = {
          ...result[subResultIdx],
          position: { x: substepBaseX, y: subHorizPrevPos?.y ?? 0 },
        }
      })
    })

    const firstLaidOut = result.find((n) => n.id === firstStep.id)
    const firstLaidOutX = firstLaidOut?.position?.x ?? firstStep.position.x
    const stepW = effectiveFlowWidth(
      firstStep.id,
      flowLabel(firstStep),
      'step',
      flowNodeTypography(firstStep),
      nodeDimensions
    )
    const topicW = effectiveFlowWidth(
      topicNode.id,
      flowLabel(topicNode),
      'topic',
      flowNodeTypography(topicNode),
      nodeDimensions
    )
    const stepCenterX = firstLaidOutX + stepW / 2
    const correctedX = Math.round(stepCenterX - topicW / 2)
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

  const claimedIds = new Set<string>([FLOW_TOPIC_NODE_ID])
  const steps = rawSteps.map((step) => {
    if (typeof step === 'string') {
      return { id: takeFlowMapStableId(claimedIds), text: step }
    }
    return { id: takeFlowMapStableId(claimedIds, step.id), text: step.text }
  })

  const substepsByStep = resolveFlowSubstepsForSteps(steps, substepsData)

  const isVertical = orientation === 'vertical'
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  const pillWidth = FLOW_MAP_PILL_WIDTH

  if (isVertical) {
    // =========================================================================
    // VERTICAL LAYOUT: Main topic at top, steps stacked vertically below
    // =========================================================================
    const stepX = DEFAULT_CENTER_X - pillWidth / 2
    const topicBox = estimateFlowPill(title, 'topic')
    const firstStepBox = steps[0] ? estimateFlowPill(steps[0].text, 'step') : null
    const stepCenterX = stepX + (firstStepBox?.boxWidth ?? pillWidth) / 2
    const topicX = Math.round(stepCenterX - topicBox.boxWidth / 2)
    const topicY = DEFAULT_PADDING + 40
    nodes.push({
      id: FLOW_TOPIC_NODE_ID,
      text: title,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: { orientation: 'vertical' },
    })

    interface SubstepGroup {
      stepId: string
      stepText: string
      stepWidth: number
      stepHeight: number
      columnHeight: number
      groupHeight: number
      substepIds: string[]
      substepTexts: string[]
      substepPositions: { id: string; y: number }[]
    }

    const substepGroups: SubstepGroup[] = steps.map((step, stepIndex) => {
      const substeps = substepsByStep[stepIndex] || []
      const stepBox = estimateFlowPill(step.text, 'step')
      const positions: { id: string; y: number }[] = []
      let cursor = 0
      substeps.forEach((item) => {
        const box = estimateFlowPill(item.text, 'substep')
        positions.push({ id: takeFlowMapStableId(claimedIds, item.id), y: cursor })
        cursor += box.boxHeight + FLOW_SUBSTEP_SPACING
      })
      const columnHeight = positions.length === 0 ? 0 : cursor - FLOW_SUBSTEP_SPACING
      return {
        stepId: step.id,
        stepText: step.text,
        stepWidth: stepBox.boxWidth,
        stepHeight: stepBox.boxHeight,
        columnHeight,
        groupHeight: Math.max(stepBox.boxHeight, columnHeight || stepBox.boxHeight),
        substepIds: positions.map((pos) => pos.id),
        substepTexts: substeps.map((item) => item.text),
        substepPositions: positions,
      }
    })

    // Position steps vertically: step on left, substeps on right.
    let currentY = topicY + topicBox.boxHeight + FLOW_TOPIC_TO_STEP_GAP

    substepGroups.forEach((group, groupIndex) => {
      const hasSubsteps = group.substepIds.length > 0
      const groupStartY = currentY

      if (hasSubsteps) {
        const stepY = groupStartY + Math.max(0, (group.columnHeight - group.stepHeight) / 2)
        const substepOrigin = groupStartY + Math.max(0, (group.stepHeight - group.columnHeight) / 2)
        const substepX = stepX + group.stepWidth + FLOW_SUBSTEP_OFFSET_X

        // Create step node with groupIndex for mindmapColors
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: stepY },
          data: {
            ...stampFlowMapStepData(groupIndex),
            [FLOW_MAP_UID_DATA_KEY]: group.stepId,
          },
        })

        // Substeps on the right of step, stacked vertically
        group.substepPositions.forEach((pos, i) => {
          const text = group.substepTexts[i] ?? ''
          nodes.push({
            id: pos.id,
            text,
            type: 'flowSubstep',
            position: { x: substepX, y: substepOrigin + pos.y },
            data: {
              ...stampFlowMapSubstepData(groupIndex, i, group.stepId),
              [FLOW_MAP_UID_DATA_KEY]: pos.id,
            },
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
          data: {
            ...stampFlowMapStepData(groupIndex),
            [FLOW_MAP_UID_DATA_KEY]: group.stepId,
          },
        })

        currentY += group.stepHeight + FLOW_MIN_STEP_SPACING
      }

      // Main flow: straight vertical line (topic -> step1 -> step2 -> step3)
      const stepColor = thinkingMapFamilyLine(groupIndex)
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

    const topicBox = estimateFlowPill(title, 'topic')
    const topicEstWidth = topicBox.boxWidth
    const topicX = DEFAULT_PADDING
    const topicY = DEFAULT_CENTER_Y - topicBox.boxHeight / 2
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
      substepEntries: {
        id?: string
        text: string
        estimatedWidth: number
        estimatedHeight: number
      }[]
      stepEstimatedWidth: number
      stepEstimatedHeight: number
      footprintWidth: number
    }

    const hGroups: HGroupInfo[] = steps.map((step, stepIndex) => {
      const subs = substepsByStep[stepIndex] || []
      const stepBox = estimateFlowPill(step.text, 'step')

      const substepEntries = subs.map((item) => {
        const box = estimateFlowPill(item.text, 'substep')
        return {
          id: item.id,
          text: item.text,
          estimatedWidth: box.boxWidth,
          estimatedHeight: box.boxHeight,
        }
      })

      const maxSubW = substepEntries.reduce((m, s) => Math.max(m, s.estimatedWidth), 0)
      return {
        stepId: step.id,
        stepText: step.text,
        substepEntries,
        stepEstimatedWidth: stepBox.boxWidth,
        stepEstimatedHeight: stepBox.boxHeight,
        footprintWidth: Math.max(stepBox.boxWidth, maxSubW),
      }
    })

    // Phase 2: Five steps per row, then a U-turn onto the next row.
    const stepStartX = DEFAULT_PADDING + topicEstWidth + FLOW_TOPIC_TO_STEP_GAP
    const hPositions = placeFlowSerpentine(
      hGroups.map((group) => ({
        footprintWidth: group.footprintWidth,
        stepWidth: group.stepEstimatedWidth,
        stepHeight: group.stepEstimatedHeight,
        belowHeight: flowSubstepStackExtent(
          group.substepEntries.map((substep) => substep.estimatedHeight)
        ),
      })),
      stepStartX,
      DEFAULT_CENTER_Y
    )

    // Phase 3: Place step nodes, substep nodes, and connections
    hGroups.forEach((group, stepIndex) => {
      const place = hPositions[stepIndex]
      const groupCenterX = place.centerX
      const stepX = place.stepX
      const groupStepY = place.stepY

      nodes.push({
        id: group.stepId,
        text: group.stepText,
        type: 'flow',
        position: { x: stepX, y: groupStepY },
        data: {
          ...stampFlowMapStepData(stepIndex),
          [FLOW_MAP_UID_DATA_KEY]: group.stepId,
        },
      })

      const stepColor = thinkingMapFamilyLine(stepIndex)
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
        const ports = flowSerpentineStepPorts(stepIndex - 1, stepIndex)
        connections.push({
          id: `edge-${prevId}-${group.stepId}`,
          source: prevId,
          target: group.stepId,
          ...ports,
          edgeType: 'straight',
          style: { strokeColor: stepColor },
        })
      }

      let subY = groupStepY + group.stepEstimatedHeight + FLOW_SUBSTEP_OFFSET_X
      group.substepEntries.forEach((substep, substepIndex) => {
        const substepId = takeFlowMapStableId(claimedIds, substep.id)
        const substepY = subY
        subY += substep.estimatedHeight + FLOW_SUBSTEP_SPACING
        const substepX = groupCenterX - substep.estimatedWidth / 2

        nodes.push({
          id: substepId,
          text: substep.text,
          type: 'flowSubstep',
          position: { x: substepX, y: substepY },
          data: {
            ...stampFlowMapSubstepData(stepIndex, substepIndex, group.stepId),
            [FLOW_MAP_UID_DATA_KEY]: substepId,
          },
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
