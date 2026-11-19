/**
 * Screen-space + handle layouts for flow-map contextual add.
 * Horizontal chain: event/step left↔right; substeps follow packing
 * (row → left↔right, stack → top↔bottom).
 * Vertical chain: top↔bottom; substeps beside a step top↔bottom.
 */
import {
  FLOW_TOPIC_NODE_ID,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
} from '@/utils/flowMapIdentity'
import type { FlowSubstepArrangement } from '@/utils/flowMapSubstepArrangement'

export type FlowMapAddAction =
  'step-before' | 'step-after' | 'substep-append' | 'substep-before' | 'substep-after'

export type FlowMapAddSelectionKind = 'topic' | 'step' | 'substep'

export type FlowMapAddHandleLayout = {
  action: FlowMapAddAction
  left: number
  top: number
}

export type FlowMapAddRect = {
  left: number
  top: number
  right: number
  bottom: number
  width: number
  height: number
}

export function resolveFlowMapAddSelectionKind(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): FlowMapAddSelectionKind | null {
  if (node.id === FLOW_TOPIC_NODE_ID || node.type === 'topic') return 'topic'
  if (isFlowMapStepNode(node)) return 'step'
  if (isFlowMapSubstepNode(node)) return 'substep'
  return null
}

/**
 * Place + handles around the selected flow node.
 * - Topic: + to the right (or below when vertical) inserts the first/next chain step.
 * - Step: left/right (or top/bottom) insert predecessor/successor; bottom (or right) appends a substep.
 * - Substep: along the packing axis — row left/right, stack (竖排) top/bottom.
 */
export function layoutFlowMapAddHandles(
  kind: FlowMapAddSelectionKind,
  orientation: 'horizontal' | 'vertical',
  rect: FlowMapAddRect,
  substepArrangement: FlowSubstepArrangement = 'row'
): FlowMapAddHandleLayout[] {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  // Stack packing and vertical chain both run substeps top→bottom.
  const substepVertical = orientation === 'vertical' || substepArrangement === 'stack'
  if (orientation === 'vertical') {
    switch (kind) {
      case 'topic':
        return [{ action: 'step-after', left: cx, top: rect.bottom }]
      case 'step':
        return [
          { action: 'step-before', left: cx, top: rect.top },
          { action: 'step-after', left: cx, top: rect.bottom },
          { action: 'substep-append', left: rect.right, top: cy },
        ]
      case 'substep':
        return [
          { action: 'substep-before', left: cx, top: rect.top },
          { action: 'substep-after', left: cx, top: rect.bottom },
        ]
    }
  }
  switch (kind) {
    case 'topic':
      return [{ action: 'step-after', left: rect.right, top: cy }]
    case 'step':
      return [
        { action: 'step-before', left: rect.left, top: cy },
        { action: 'substep-append', left: cx, top: rect.bottom },
        { action: 'step-after', left: rect.right, top: cy },
      ]
    case 'substep':
      if (substepVertical) {
        return [
          { action: 'substep-before', left: cx, top: rect.top },
          { action: 'substep-after', left: cx, top: rect.bottom },
        ]
      }
      return [
        { action: 'substep-before', left: rect.left, top: cy },
        { action: 'substep-after', left: rect.right, top: cy },
      ]
  }
}
