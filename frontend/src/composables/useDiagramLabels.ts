/**
 * useDiagramLabels - Diagram type to display name mapping
 * Used for placeholder text like "新圆圈图" / "New Circle Map" when creating new diagrams
 */
import type { DiagramType } from '@/types'

const DIAGRAM_TYPE_LABELS: Record<string, { zh: string; en: string }> = {
  circle_map: { zh: '圆圈图', en: 'Circle Map' },
  bubble_map: { zh: '气泡图', en: 'Bubble Map' },
  double_bubble_map: { zh: '双气泡图', en: 'Double Bubble Map' },
  tree_map: { zh: '树形图', en: 'Tree Map' },
  brace_map: { zh: '括号图', en: 'Brace Map' },
  flow_map: { zh: '流程图', en: 'Flow Map' },
  multi_flow_map: { zh: '复流程图', en: 'Multi-Flow Map' },
  bridge_map: { zh: '桥形图', en: 'Bridge Map' },
  mindmap: { zh: '思维导图', en: 'Mind Map' },
  mind_map: { zh: '思维导图', en: 'Mind Map' },
  concept_map: { zh: '概念图', en: 'Concept Map' },
}

/**
 * Get display name for a diagram type (handles both type key and Chinese name)
 * @param typeOrName - Diagram type key (circle_map) or Chinese name (圆圈图)
 * @param isZh - Whether to return Chinese or English label
 */
export function getDiagramTypeDisplayName(typeOrName: string, isZh: boolean): string {
  const labels = DIAGRAM_TYPE_LABELS[typeOrName]
  if (labels) {
    return isZh ? labels.zh : labels.en
  }
  return typeOrName
}

/**
 * Generate default diagram name for new diagrams
 * Format: "新圆圈图" / "New Circle Map"
 */
export function getDefaultDiagramName(
  diagramType: DiagramType | string | null,
  isZh: boolean
): string {
  const displayName = diagramType ? getDiagramTypeDisplayName(diagramType, isZh) : ''
  if (!displayName) {
    return isZh ? '新图示' : 'New Diagram'
  }
  return isZh ? `新${displayName}` : `New ${displayName}`
}
