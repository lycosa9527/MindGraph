import type { DiagramType } from '@/types'

/** Map Chinese diagram type names (UI store) to DiagramType */
export const diagramTypeMap: Record<string, DiagramType> = {
  圆圈图: 'circle_map',
  气泡图: 'bubble_map',
  双气泡图: 'double_bubble_map',
  树形图: 'tree_map',
  括号图: 'brace_map',
  流程图: 'flow_map',
  复流程图: 'multi_flow_map',
  桥形图: 'bridge_map',
  思维导图: 'mindmap',
  概念图: 'concept_map',
}

/** Reverse map: DiagramType to Chinese name (for UI store sync) */
export const diagramTypeToChineseMap: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

export const VALID_DIAGRAM_TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'mind_map',
  'concept_map',
]

/**
 * Sync canvas chrome (toolbar / top-bar actions) to a known diagram type before
 * `loadFromSpec` finishes. Avoids a flash of the previous diagram's toolbar
 * while the library fetch / markdown pipeline is still in flight.
 */
export function applyDiagramTypeForCanvasChrome(
  setDiagramType: (diagramType: DiagramType) => boolean,
  diagramType: string | null | undefined
): boolean {
  if (!diagramType || !VALID_DIAGRAM_TYPES.includes(diagramType as DiagramType)) {
    return false
  }
  return setDiagramType(diagramType as DiagramType)
}
