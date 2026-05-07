/**
 * useDiagramLabels - Diagram type to display name mapping
 * Used for placeholder text like "新圆圈图" / "New Circle Map" when creating new diagrams.
 * zh / zh-tw use Chinese; az / fr / af / si use locale columns; others fall back to labels.en until extended.
 */
import type { LocaleCode } from '@/i18n/locales'
import type { DiagramType } from '@/types'

const DIAGRAM_TYPE_LABELS: Record<
  string,
  { zh: string; en: string; az: string; fr: string; af: string; si: string }
> = {
  circle_map: {
    zh: '圆圈图',
    en: 'Circle Map',
    az: 'Dairə xəritəsi',
    fr: 'Carte circulaire',
    af: 'Sirkelkaart',
    si: 'වෘත්ත සිතියම',
  },
  bubble_map: {
    zh: '气泡图',
    en: 'Bubble Map',
    az: 'Baloncuk xəritəsi',
    fr: 'Carte à bulles',
    af: 'Borrelkaart',
    si: 'බුබුල සිතියම',
  },
  double_bubble_map: {
    zh: '双气泡图',
    en: 'Double Bubble Map',
    az: 'İki baloncuk xəritəsi',
    fr: 'Double carte à bulles',
    af: 'Dubbelborrelkaart',
    si: 'ද්විත්ව බුබුල සිතියම',
  },
  tree_map: {
    zh: '树形图',
    en: 'Tree Map',
    az: 'Ağac xəritəsi',
    fr: 'Carte arborescente',
    af: 'Boomkaart',
    si: 'රුක් සිතියම',
  },
  brace_map: {
    zh: '括号图',
    en: 'Brace Map',
    az: 'Mötərizə xəritəsi',
    fr: 'Carte en accolades',
    af: 'Krulhakiekaart',
    si: 'බ්‍රේස් සිතියම',
  },
  flow_map: {
    zh: '流程图',
    en: 'Flow Map',
    az: 'Axın xəritəsi',
    fr: 'Carte de flux',
    af: 'Vloei-kaart',
    si: 'ප්‍රවාහ සිතියම',
  },
  multi_flow_map: {
    zh: '复流程图',
    en: 'Multi-Flow Map',
    az: 'Çox axın xəritəsi',
    fr: 'Carte multi-flux',
    af: 'Multivloei-kaart',
    si: 'බහු ප්‍රවාහ සිතියම',
  },
  bridge_map: {
    zh: '桥形图',
    en: 'Bridge Map',
    az: 'Körpü xəritəsi',
    fr: 'Carte en pont',
    af: 'Brugkaart',
    si: 'පාලම සිතියම',
  },
  mindmap: {
    zh: '思维导图',
    en: 'Mind Map',
    az: 'Zehin xəritəsi',
    fr: 'Carte mentale',
    af: 'Denkkaart',
    si: 'මනෝ සිතියම',
  },
  mind_map: {
    zh: '思维导图',
    en: 'Mind Map',
    az: 'Zehin xəritəsi',
    fr: 'Carte mentale',
    af: 'Denkkaart',
    si: 'මනෝ සිතියම',
  },
  concept_map: {
    zh: '概念图',
    en: 'Concept Map',
    az: 'Konsept xəritəsi',
    fr: 'Carte conceptuelle',
    af: 'Konsepkaart',
    si: 'සංකල්ප සිතියම',
  },
}

function pickLocale(
  labels: { zh: string; en: string; az: string; fr: string; af: string; si: string },
  locale: LocaleCode
): string {
  if (locale === 'zh' || locale === 'zh-tw') return labels.zh
  if (locale === 'az') return labels.az
  if (locale === 'fr') return labels.fr
  if (locale === 'af') return labels.af
  if (locale === 'si') return labels.si
  return labels.en
}

const NEW_EN = 'New Diagram'

const NEW_DIAGRAM_FALLBACK: Record<LocaleCode, string> = {
  'zh-tw': '新圖示',
  zh: '新图示',
  en: NEW_EN,
  az: 'Yeni diaqram',
  th: NEW_EN,
  fr: 'Nouveau diagramme',
  de: NEW_EN,
  dv: NEW_EN,
  ja: NEW_EN,
  ko: NEW_EN,
  pt: NEW_EN,
  ru: NEW_EN,
  ar: NEW_EN,
  nl: NEW_EN,
  it: NEW_EN,
  hi: NEW_EN,
  id: NEW_EN,
  vi: NEW_EN,
  tr: NEW_EN,
  pl: NEW_EN,
  ps: NEW_EN,
  uk: NEW_EN,
  ms: NEW_EN,
  es: NEW_EN,
  et: NEW_EN,
  sv: NEW_EN,
  da: NEW_EN,
  fi: NEW_EN,
  no: NEW_EN,
  cs: NEW_EN,
  ro: NEW_EN,
  el: NEW_EN,
  he: NEW_EN,
  fa: NEW_EN,
  sw: NEW_EN,
  tl: NEW_EN,
  bn: NEW_EN,
  bs: NEW_EN,
  ta: NEW_EN,
  ca: NEW_EN,
  bg: NEW_EN,
  hr: NEW_EN,
  hu: NEW_EN,
  hy: NEW_EN,
  am: NEW_EN,
  ka: NEW_EN,
  km: NEW_EN,
  kk: NEW_EN,
  ky: NEW_EN,
  lo: NEW_EN,
  lt: NEW_EN,
  lv: NEW_EN,
  mk: NEW_EN,
  ml: NEW_EN,
  mn: NEW_EN,
  my: NEW_EN,
  ne: NEW_EN,
  si: 'නව සිතියම',
  sk: NEW_EN,
  sl: NEW_EN,
  sq: NEW_EN,
  sr: NEW_EN,
  tg: NEW_EN,
  tk: NEW_EN,
  ug: NEW_EN,
  ur: NEW_EN,
  uz: NEW_EN,
  af: 'Nuwe diagram',
  ha: NEW_EN,
  ig: NEW_EN,
  so: NEW_EN,
  ss: NEW_EN,
  st: NEW_EN,
  tn: NEW_EN,
  xh: NEW_EN,
  yo: NEW_EN,
  zu: NEW_EN,
}

/**
 * Get display name for a diagram type (handles both type key and Chinese name)
 * @param typeOrName - Diagram type key (circle_map) or Chinese name (圆圈图)
 * @param locale - UI locale
 */
export function getDiagramTypeDisplayName(typeOrName: string, locale: LocaleCode): string {
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
  if (locale === 'zh' || locale === 'zh-tw') {
    return `新${displayName}`
  }
  if (locale === 'az') {
    return `Yeni ${displayName}`
  }
  if (locale === 'fr') {
    return `Nouveau ${displayName}`
  }
  if (locale === 'af') {
    return `Nuwe ${displayName}`
  }
  if (locale === 'si') {
    return `නව ${displayName}`
  }
  return `New ${displayName}`
}
