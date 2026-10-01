/**
 * Which node-palette stage a selected thinking-map node should open.
 * Flat maps stay on the palette default. Staged maps focus that parent.
 */
import {
  buildStageDataForParent,
  getStage2ParentsForDiagram,
  stage2StageNameForType,
} from '@/composables/nodePalette/stageHelpers'
import type { DiagramType } from '@/types'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'

export type ThinkingMapPaletteMode = 'similarities' | 'differences' | 'causes' | 'effects'

export type ThinkingMapPaletteFocus =
  | { kind: 'mode'; mode: ThinkingMapPaletteMode }
  | {
      kind: 'parent'
      id: string
      name: string
      stage: string
      stageData: Record<string, unknown>
    }

type FocusNode = {
  id?: string
  text?: string
  type?: string
  data?: Record<string, unknown>
}

export function thinkingMapPaletteFocus(options: {
  diagramType: string | null | undefined
  nodes: FocusNode[]
  connections?: Array<{ source: string; target: string }>
  nodeId: string
  dimension?: string | null
}): ThinkingMapPaletteFocus | null {
  const diagramType = options.diagramType === 'mind_map' ? 'mindmap' : options.diagramType
  if (!diagramType || diagramType === 'mindmap') return null
  const node = options.nodes.find((item) => item.id === options.nodeId)
  if (!node) return null

  if (diagramType === 'double_bubble_map') {
    const role = readDoubleBubbleRole(node)
    if (role === 'similarity') return { kind: 'mode', mode: 'similarities' }
    if (role === 'leftDiff' || role === 'rightDiff') return { kind: 'mode', mode: 'differences' }
    return null
  }
  if (diagramType === 'multi_flow_map') {
    if (isMultiFlowCauseNode(node)) return { kind: 'mode', mode: 'causes' }
    if (isMultiFlowEffectNode(node)) return { kind: 'mode', mode: 'effects' }
    return null
  }

  const typed = diagramType as DiagramType
  const parent = getStage2ParentsForDiagram(typed, options.nodes, options.connections).find(
    (item) => item.id === options.nodeId
  )
  const stage = stage2StageNameForType(typed)
  if (!parent || !stage) return null
  return {
    kind: 'parent',
    id: parent.id,
    name: parent.name,
    stage,
    stageData: buildStageDataForParent(parent, typed, {
      dimension: options.dimension ?? '',
    }),
  }
}
