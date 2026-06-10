/**
 * Shared diagram type key mapping (Chinese UI keys ↔ DiagramType).
 * Matches keys in uiStore DIAGRAM_TEMPLATES.
 */
import type { DiagramType } from '@/types'

export const DEFAULT_CHART_TYPE_KEY = '选择具体图示'

export const DIAGRAM_TYPE_KEY_TO_TYPE: Record<string, DiagramType> = {
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

export const DIAGRAM_TYPE_TO_KEY: Record<DiagramType, string> = {
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

export function diagramTypeFromKey(key: string | null | undefined): DiagramType | null {
  if (!key || key === DEFAULT_CHART_TYPE_KEY) {
    return null
  }
  return DIAGRAM_TYPE_KEY_TO_TYPE[key] ?? null
}

export function diagramTypeKeyForType(type: DiagramType): string | null {
  return DIAGRAM_TYPE_TO_KEY[type] ?? null
}

export function diagramTypeKeyFromDiagramType(type: string): string | null {
  if (type in DIAGRAM_TYPE_TO_KEY) {
    return DIAGRAM_TYPE_TO_KEY[type as DiagramType]
  }
  return Object.entries(DIAGRAM_TYPE_KEY_TO_TYPE).find(([, v]) => v === type)?.[0] ?? null
}
