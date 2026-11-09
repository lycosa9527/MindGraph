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

/** Vertical layout: the topic sits this far below the canvas top. */
const FLOW_VERTICAL_TOPIC_Y = DEFAULT_PADDING + 40
/** Vertical layout: left edge of the step column. */
const FLOW_VERTICAL_STEP_X = DEFAULT_CENTER_X - FLOW_MAP_PILL_WIDTH / 2

/**
 * Live layout for flow maps. Uses DOM-measured node dimensions from Pinia,
 * falling back to the text estimate for a node not measured yet, to:
 * - Horizontal layout: place steps on the serpentine after the topic and
 *   correct topic Y so its center matches the first step's center Y.
 * - Vertical layout: stack step (and substep) groups under the topic using
 *   measured heights so wrapped text does not overlap, then center the topic
 *   over the step column.
 * The topic keeps its X (horizontal) or Y (vertical) and vertical steps keep
 * their X; everything else is derived, so running the layout on its own output
 * does not move any node.
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
  const indexById = new Map(result.map((n, index) => [n.id, index]))
  const moveTo = (id: string, position: { x: number; y: number }): void => {
    const index = indexById.get(id)
    if (index !== undefined) result[index] = { ...result[index], position }
  }
  const substepNodes = result.filter((n) => n.type === 'flowSubstep')
  const widthOf = (node: DiagramNode, role: FlowPillRole): number =>
    effectiveFlowWidth(node.id, flowLabel(node), role, flowNodeTypography(node), nodeDimensions)
  const heightOf = (node: DiagramNode, role: FlowPillRole): number =>
    flowBoxHeight(node, role, nodeDimensions[node.id]?.height, flowLabel(node))
  const topicH = heightOf(topicNode, 'topic')

  if (orientation === 'horizontal') {
    const groups = stepNodes.map((stepNode) => {
      const groupSubsteps = substepsForFlowStep(substepNodes, stepNode).map((sub) => ({
        node: sub,
        width: widthOf(sub, 'substep'),
        height: heightOf(sub, 'substep'),
      }))
      const stepW = widthOf(stepNode, 'step')
      const maxSubW = groupSubsteps.reduce((maxW, sub) => Math.max(maxW, sub.width), 0)
      return {
        stepNode,
        stepW,
        stepH: heightOf(stepNode, 'step'),
        groupSubsteps,
        footprintWidth: Math.max(stepW, maxSubW),
      }
    })

    const topicEstW = estimateFlowPill(
      flowLabel(topicNode),
      'topic',
      flowNodeTypography(topicNode)
    ).boxWidth
    const effectiveTopicW = flowCenteringWidth(topicDims?.width, topicEstW)

    const placed = placeFlowSerpentine(
      groups.map((group) => ({
        footprintWidth: group.footprintWidth,
        stepWidth: group.stepW,
        stepHeight: group.stepH,
        belowHeight: flowSubstepStackExtent(group.groupSubsteps.map((sub) => sub.height)),
      })),
      topicNode.position.x + effectiveTopicW + FLOW_TOPIC_TO_STEP_GAP,
      DEFAULT_CENTER_Y
    )
    groups.forEach((group, index) => {
      const place = placed[index]
      const stepY = Math.round(place.stepY)
      moveTo(group.stepNode.id, { x: Math.round(place.stepX), y: stepY })

      let subY = stepY + group.stepH + FLOW_SUBSTEP_OFFSET_X
      group.groupSubsteps.forEach((sub) => {
        moveTo(sub.node.id, { x: Math.round(place.centerX - sub.width / 2), y: subY })
        subY += sub.height + FLOW_SUBSTEP_SPACING
      })
    })

    const firstGroup = groups[0]
    const firstStepY = Math.round(placed[0].stepY)
    moveTo(FLOW_TOPIC_NODE_ID, {
      x: topicNode.position.x,
      y: Math.round(firstStepY + firstGroup.stepH / 2 - topicH / 2),
    })
    return result
  }

  // Vertical: steps on the left, substeps stacked to their right.
  let currentY = topicNode.position.y + topicH + FLOW_TOPIC_TO_STEP_GAP
  stepNodes.forEach((stepNode) => {
    const stepX = stepNode.position?.x ?? 0
    const stepH = heightOf(stepNode, 'step')
    const groupSubsteps = substepsForFlowStep(substepNodes, stepNode)
    if (groupSubsteps.length === 0) {
      moveTo(stepNode.id, { x: stepX, y: currentY })
      currentY += stepH + FLOW_MIN_STEP_SPACING
      return
    }
    const subHeights = groupSubsteps.map((sub) => heightOf(sub, 'substep'))
    const substepColumnH =
      subHeights.reduce((sum, h) => sum + h, 0) + FLOW_SUBSTEP_SPACING * (subHeights.length - 1)
    moveTo(stepNode.id, {
      x: stepX,
      y: Math.round(currentY + Math.max(0, (substepColumnH - stepH) / 2)),
    })
    const substepX = stepX + widthOf(stepNode, 'step') + FLOW_SUBSTEP_OFFSET_X
    let subY = Math.round(currentY + Math.max(0, (stepH - substepColumnH) / 2))
    groupSubsteps.forEach((sub, index) => {
      moveTo(sub.id, { x: substepX, y: subY })
      subY += subHeights[index] + FLOW_SUBSTEP_SPACING
    })
    currentY += Math.max(stepH, substepColumnH) + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
  })

  const stepCenterX = firstStep.position.x + widthOf(firstStep, 'step') / 2
  moveTo(FLOW_TOPIC_NODE_ID, {
    x: Math.round(stepCenterX - widthOf(topicNode, 'topic') / 2),
    y: topicNode.position.y,
  })
  return result
}

function flowStepEdge(
  sourceId: string,
  targetId: string,
  stepIndex: number,
  isVertical: boolean
): Connection {
  const ports = isVertical
    ? {
        sourcePosition: 'bottom' as const,
        targetPosition: 'top' as const,
        sourceHandle: 'bottom',
        targetHandle: 'top',
      }
    : stepIndex === 0
      ? {
          sourcePosition: 'right' as const,
          targetPosition: 'left' as const,
          sourceHandle: 'right',
          targetHandle: 'left',
        }
      : flowSerpentineStepPorts(stepIndex - 1, stepIndex)
  return {
    id: `edge-${sourceId}-${targetId}`,
    source: sourceId,
    target: targetId,
    ...ports,
    edgeType: 'straight',
    style: { strokeColor: thinkingMapFamilyLine(stepIndex) },
  }
}

function flowSubstepEdge(
  stepId: string,
  substepId: string,
  stepIndex: number,
  isVertical: boolean
): Connection {
  const routing = isVertical
    ? {
        sourcePosition: 'right' as const,
        targetPosition: 'left' as const,
        sourceHandle: 'substep-source',
        targetHandle: 'left',
        edgeType: 'curved' as const,
      }
    : {
        sourcePosition: 'bottom' as const,
        targetPosition: 'top' as const,
        sourceHandle: 'center-source',
        targetHandle: 'center-target',
        edgeType: 'tree' as const,
      }
  return {
    id: `edge-${stepId}-${substepId}`,
    source: stepId,
    target: substepId,
    ...routing,
    style: { strokeColor: thinkingMapFamilyLine(stepIndex) },
  }
}

/**
 * Build flow map nodes and connections from a spec, then place them with
 * {@link recalculateFlowMapLayout} on text estimates.
 */
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

  // Topic seed; the layout pass moves it once there is a step to align with.
  const topicBox = estimateFlowPill(title, 'topic')
  nodes.push({
    id: FLOW_TOPIC_NODE_ID,
    text: title,
    type: 'topic',
    position: isVertical
      ? { x: Math.round(DEFAULT_CENTER_X - topicBox.boxWidth / 2), y: FLOW_VERTICAL_TOPIC_Y }
      : { x: DEFAULT_PADDING, y: DEFAULT_CENTER_Y - topicBox.boxHeight / 2 },
    data: { orientation: isVertical ? 'vertical' : 'horizontal' },
  })

  steps.forEach((step, stepIndex) => {
    nodes.push({
      id: step.id,
      text: step.text,
      type: 'flow',
      position: { x: isVertical ? FLOW_VERTICAL_STEP_X : 0, y: 0 },
      data: {
        ...stampFlowMapStepData(stepIndex),
        [FLOW_MAP_UID_DATA_KEY]: step.id,
      },
    })
    const sourceId = stepIndex === 0 ? FLOW_TOPIC_NODE_ID : steps[stepIndex - 1].id
    connections.push(flowStepEdge(sourceId, step.id, stepIndex, isVertical))

    ;(substepsByStep[stepIndex] || []).forEach((item, substepIndex) => {
      const substepId = takeFlowMapStableId(claimedIds, item.id)
      nodes.push({
        id: substepId,
        text: item.text,
        type: 'flowSubstep',
        position: { x: 0, y: 0 },
        data: {
          ...stampFlowMapSubstepData(stepIndex, substepIndex, step.id),
          [FLOW_MAP_UID_DATA_KEY]: substepId,
        },
      })
      connections.push(flowSubstepEdge(step.id, substepId, stepIndex, isVertical))
    })
  })

  return {
    nodes: recalculateFlowMapLayout(nodes),
    connections,
    metadata: { orientation },
  }
}
