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
  FLOW_SUBSTEP_PILL_MIN_WIDTH,
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
  type FlowSubstepArrangement,
  normalizeFlowSubstepArrangement,
  resolveFlowMapSubstepArrangement,
} from '@/utils/flowMapSubstepArrangement'
import {
  type FlowPillFont,
  type FlowPillRole,
  flowSecondaryExtraHeight,
  measureFlowRolePill,
} from '@/utils/flowPillBox'
import { MEASURED_BOX_COLLAPSE_SLACK_PX, measuredBoxExtent } from '@/utils/measuredBoxExtent'
import { textWithIconAdornment } from '@/utils/mindMapAdornments'
import { thinkingMapFamilyLine } from '@/utils/thinkingMapChrome'

import {
  flowSerpentineStepPorts,
  flowSubstepRowExtent,
  flowSubstepRowWidth,
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
function flowCenteringWidth(
  measured: number | undefined,
  estimated: number,
  floor = FLOW_MAP_PILL_WIDTH
): number {
  return measuredBoxExtent(measured, estimated, floor)
}

function effectiveFlowWidth(
  nodeId: string,
  text: string,
  role: FlowPillRole,
  font: FlowPillFont,
  nodeDimensions: Record<string, { width: number; height: number }>
): number {
  const floor = role === 'substep' ? FLOW_SUBSTEP_PILL_MIN_WIDTH : FLOW_MAP_PILL_WIDTH
  return flowCenteringWidth(
    nodeDimensions[nodeId]?.width,
    estimateFlowPill(text, role, font).boxWidth,
    floor
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
  const substepArrangement = resolveFlowMapSubstepArrangement(topicNode)

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
      const subWidths = groupSubsteps.map((sub) => sub.width)
      const subHeights = groupSubsteps.map((sub) => sub.height)
      const rowW = flowSubstepRowWidth(subWidths)
      // Intrinsic text width only — never the previously forced stretch from DOM measure.
      const textStepW = estimateFlowPill(
        flowLabel(stepNode),
        'step',
        flowNodeTypography(stepNode)
      ).boxWidth
      const measuredStepW = nodeDimensions[stepNode.id]?.width
      // Trust a measured width when it looks like real text (narrower than the row).
      const contentStepW =
        measuredStepW != null &&
        measuredStepW > textStepW &&
        (groupSubsteps.length === 0 || measuredStepW < rowW - 1)
          ? measuredStepW
          : textStepW
      // Row mode: stretch the step pill to cover its substep row.
      const stepW =
        substepArrangement === 'row' && groupSubsteps.length > 0
          ? Math.max(contentStepW, rowW)
          : widthOf(stepNode, 'step')
      const footprintWidth =
        substepArrangement === 'row'
          ? Math.max(stepW, rowW)
          : Math.max(
              stepW,
              subWidths.reduce((maxW, width) => Math.max(maxW, width), 0)
            )
      const belowHeight =
        substepArrangement === 'row'
          ? flowSubstepRowExtent(subHeights)
          : flowSubstepStackExtent(subHeights)
      return {
        stepNode,
        stepW,
        stretchToRow: substepArrangement === 'row' && groupSubsteps.length > 0,
        stepH: heightOf(stepNode, 'step'),
        groupSubsteps,
        footprintWidth,
        belowHeight,
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
        belowHeight: group.belowHeight,
      })),
      topicNode.position.x + effectiveTopicW + FLOW_TOPIC_TO_STEP_GAP,
      DEFAULT_CENTER_Y
    )
    groups.forEach((group, index) => {
      const place = placed[index]
      const stepY = Math.round(place.stepY)
      const stepIndex = indexById.get(group.stepNode.id)
      if (stepIndex !== undefined) {
        const prev = result[stepIndex]
        const nextStyle = { ...(prev.style || {}) }
        if (group.stretchToRow) {
          nextStyle.width = group.stepW
          nextStyle.minWidth = group.stepW
        } else {
          delete nextStyle.width
          delete nextStyle.minWidth
        }
        result[stepIndex] = {
          ...prev,
          position: { x: Math.round(place.stepX), y: stepY },
          style: nextStyle,
        }
      }

      if (group.groupSubsteps.length === 0) return
      const subY = stepY + group.stepH + FLOW_SUBSTEP_OFFSET_X
      if (substepArrangement === 'row') {
        const rowW = flowSubstepRowWidth(group.groupSubsteps.map((sub) => sub.width))
        let subX = Math.round(place.centerX - rowW / 2)
        group.groupSubsteps.forEach((sub) => {
          moveTo(sub.node.id, { x: subX, y: subY })
          subX += sub.width + FLOW_SUBSTEP_SPACING
        })
        return
      }
      let stackY = subY
      group.groupSubsteps.forEach((sub) => {
        moveTo(sub.node.id, { x: Math.round(place.centerX - sub.width / 2), y: stackY })
        stackY += sub.height + FLOW_SUBSTEP_SPACING
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

  // Vertical: one centered spine of steps; substeps stack to the right of each step.
  // Do not keep horizontal-row stretch widths — they skew centers and bend the spine.
  const verticalGroups = stepNodes.map((stepNode) => {
    const groupSubsteps = substepsForFlowStep(substepNodes, stepNode).map((sub) => ({
      node: sub,
      width: widthOf(sub, 'substep'),
      height: heightOf(sub, 'substep'),
    }))
    const estimatedW = estimateFlowPill(
      flowLabel(stepNode),
      'step',
      flowNodeTypography(stepNode)
    ).boxWidth
    const measuredW = nodeDimensions[stepNode.id]?.width
    // Drop leftover row-stretch measures (much wider than the label).
    const stepW =
      measuredW != null && measuredW <= estimatedW + MEASURED_BOX_COLLAPSE_SLACK_PX * 2
        ? measuredW
        : estimatedW
    return {
      stepNode,
      stepW,
      stepH: heightOf(stepNode, 'step'),
      groupSubsteps,
    }
  })

  const topicW = widthOf(topicNode, 'topic')
  const spineCenterX = DEFAULT_CENTER_X
  let currentY = Math.round(
    (topicNode.position?.y ?? FLOW_VERTICAL_TOPIC_Y) + topicH + FLOW_TOPIC_TO_STEP_GAP
  )

  verticalGroups.forEach((group) => {
    const stepIndex = indexById.get(group.stepNode.id)
    const stepX = Math.round(spineCenterX - group.stepW / 2)
    const subHeights = group.groupSubsteps.map((sub) => sub.height)
    const substepColumnH =
      subHeights.length === 0
        ? 0
        : subHeights.reduce((sum, h) => sum + h, 0) + FLOW_SUBSTEP_SPACING * (subHeights.length - 1)
    const blockH = Math.max(group.stepH, substepColumnH)
    const stepY = Math.round(currentY + Math.max(0, (blockH - group.stepH) / 2))

    if (stepIndex !== undefined) {
      const prev = result[stepIndex]
      const nextStyle = { ...(prev.style || {}) }
      delete nextStyle.width
      delete nextStyle.minWidth
      result[stepIndex] = {
        ...prev,
        position: { x: stepX, y: stepY },
        style: nextStyle,
      }
    }

    if (group.groupSubsteps.length > 0) {
      const substepX = stepX + group.stepW + FLOW_SUBSTEP_OFFSET_X
      let subY = Math.round(currentY + Math.max(0, (blockH - substepColumnH) / 2))
      group.groupSubsteps.forEach((sub, index) => {
        moveTo(sub.node.id, { x: substepX, y: subY })
        subY += subHeights[index] + FLOW_SUBSTEP_SPACING
      })
    }

    currentY += blockH + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
  })

  moveTo(FLOW_TOPIC_NODE_ID, {
    x: Math.round(spineCenterX - topicW / 2),
    y: Math.round(topicNode.position?.y ?? FLOW_VERTICAL_TOPIC_Y),
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
        sourceHandle: 'bottom',
        targetHandle: 'top-target',
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
  const substepArrangement = normalizeFlowSubstepArrangement(spec.substepArrangement)
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
    data: {
      orientation: isVertical ? 'vertical' : 'horizontal',
      substepArrangement,
    },
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
    metadata: { orientation, substepArrangement },
  }
}

export type { FlowSubstepArrangement }
