/**
 * Flow-map substep packing under each step (orthogonal to main-chain orientation).
 * - stack: substeps stacked vertically under / beside the step (legacy default look)
 * - row: substeps in a horizontal row under the step (classroom-normative)
 *
 * Toolbar structure modes also include main-chain vertical as a third option.
 */

export type FlowSubstepArrangement = 'stack' | 'row'

/** Combined structure picker: horizontal row / horizontal stack / vertical chain. */
export type FlowMapStructureMode = FlowSubstepArrangement | 'vertical'

export const DEFAULT_FLOW_SUBSTEP_ARRANGEMENT: FlowSubstepArrangement = 'row'

export function normalizeFlowSubstepArrangement(value: unknown): FlowSubstepArrangement {
  return value === 'stack' ? 'stack' : 'row'
}

export function normalizeFlowMapStructureMode(value: unknown): FlowMapStructureMode {
  if (value === 'vertical' || value === 'stack' || value === 'row') return value
  return DEFAULT_FLOW_SUBSTEP_ARRANGEMENT
}

export function resolveFlowMapSubstepArrangement(
  topicNode: { data?: Record<string, unknown> } | undefined,
  diagramData?: Record<string, unknown> | null
): FlowSubstepArrangement {
  const fromTopic = topicNode?.data?.substepArrangement
  if (fromTopic === 'stack' || fromTopic === 'row') return fromTopic
  const fromData = diagramData?.substepArrangement
  if (fromData === 'stack' || fromData === 'row') return fromData
  return DEFAULT_FLOW_SUBSTEP_ARRANGEMENT
}

function resolveFlowMapChainOrientation(
  topicNode: { data?: Record<string, unknown> } | undefined,
  diagramData?: Record<string, unknown> | null
): 'horizontal' | 'vertical' {
  const fromTopic = topicNode?.data?.orientation
  if (fromTopic === 'vertical' || fromTopic === 'horizontal') return fromTopic
  const fromData = diagramData?.orientation
  if (fromData === 'vertical' || fromData === 'horizontal') return fromData
  return 'horizontal'
}

/** Active structure-dropdown mode for the flow-map toolbar. */
export function resolveFlowMapStructureMode(
  topicNode: { data?: Record<string, unknown> } | undefined,
  diagramData?: Record<string, unknown> | null
): FlowMapStructureMode {
  if (resolveFlowMapChainOrientation(topicNode, diagramData) === 'vertical') return 'vertical'
  return resolveFlowMapSubstepArrangement(topicNode, diagramData)
}
