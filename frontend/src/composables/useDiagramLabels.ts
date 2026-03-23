/**
 * useDiagramLabels - Diagram type to display name mapping
 * Used for placeholder text like "新圆圈图" / "New Circle Map" / Azerbaijani when creating new diagrams
 */
import type { LocaleCode } from '@/i18n/locales'

import type { DiagramType } from '@/types'

const DIAGRAM_TYPE_LABELS: Record<
  string,
  { zh: string; en: string; az: string }
> = {
  circle_map: { zh: '圆圈图', en: 'Circle Map', az: 'Dairə xəritəsi' },
  bubble_map: { zh: '气泡图', en: 'Bubble Map', az: 'Baloncuk xəritəsi' },
  double_bubble_map: { zh: '双气泡图', en: 'Double Bubble Map', az: 'İki baloncuk xəritəsi' },
  tree_map: { zh: '树形图', en: 'Tree Map', az: 'Ağac xəritəsi' },
  brace_map: { zh: '括号图', en: 'Brace Map', az: 'Mötərizə xəritəsi' },
  flow_map: { zh: '流程图', en: 'Flow Map', az: 'Axın xəritəsi' },
  multi_flow_map: { zh: '复流程图', en: 'Multi-Flow Map', az: 'Çox axın xəritəsi' },
  bridge_map: { zh: '桥形图', en: 'Bridge Map', az: 'Körpü xəritəsi' },
  mindmap: { zh: '思维导图', en: 'Mind Map', az: 'Zehin xəritəsi' },
  mind_map: { zh: '思维导图', en: 'Mind Map', az: 'Zehin xəritəsi' },
  concept_map: { zh: '概念图', en: 'Concept Map', az: 'Konsept xəritəsi' },
}

function pickLocale(
  labels: { zh: string; en: string; az: string },
  locale: LocaleCode
): string {
  if (locale === 'zh') return labels.zh
  if (locale === 'az') return labels.az
  return labels.en
}

const NEW_DIAGRAM_FALLBACK: Record<LocaleCode, string> = {
  zh: '新图示',
  en: 'New Diagram',
  az: 'Yeni diaqram',
}

/**
 * Get display name for a diagram type (handles both type key and Chinese name)
 * @param typeOrName - Diagram type key (circle_map) or Chinese name (圆圈图)
 * @param locale - UI locale (zh / en / az)
 */
export function getDiagramTypeDisplayName(
  typeOrName: string,
  locale: LocaleCode
): string {
  const labels = DIAGRAM_TYPE_LABELS[typeOrName]
  if (labels) {
    return pickLocale(labels, locale)
  }
  return typeOrName
}

/**
 * Generate default diagram name for new diagrams
 * Format: "新圆圈图" / "New Circle Map" / "Yeni Dairə xəritəsi"
 */
export function getDefaultDiagramName(
  diagramType: DiagramType | string | null,
  locale: LocaleCode
): string {
  const displayName = diagramType ? getDiagramTypeDisplayName(diagramType, locale) : ''
  if (!displayName) {
    return NEW_DIAGRAM_FALLBACK[locale] ?? NEW_DIAGRAM_FALLBACK.en
  }
  if (locale === 'zh') {
    return `新${displayName}`
  }
  if (locale === 'az') {
    return `Yeni ${displayName}`
  }
  return `New ${displayName}`
}
