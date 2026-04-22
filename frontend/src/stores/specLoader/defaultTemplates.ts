/**
 * Default diagram specs for new / blank canvas — fully i18n-driven.
 * All node labels resolve through vue-i18n so every UI locale gets native text.
 */
import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { getConceptMapFocusQuestionDefault } from '@/stores/diagram/diagramDefaultLabels'
import type { DiagramType } from '@/types'

function lt(key: string, lang: LocaleCode, params?: Record<string, unknown>): string {
  return String(i18n.global.t(key, params ?? {}, { locale: lang }))
}

function range(count: number, key: string, lang: LocaleCode): string[] {
  return Array.from({ length: count }, (_, i) => lt(key, lang, { n: i + 1 }))
}

function templatesForLocale(lang: LocaleCode): Record<string, Record<string, unknown>> {
  const fq = getConceptMapFocusQuestionDefault(lang)

  return {
    circle_map: {
      topic: lt('diagram.defaults.topic', lang),
      context: range(8, 'diagram.defaults.contextN', lang),
    },
    bubble_map: {
      topic: lt('diagram.defaults.topic', lang),
      attributes: range(5, 'diagram.defaults.attributeN', lang),
    },
    double_bubble_map: {
      left: lt('diagram.defaults.topicA', lang),
      right: lt('diagram.defaults.topicB', lang),
      similarities: range(2, 'diagram.doubleBubble.similarityN', lang),
      left_differences: range(3, 'diagram.doubleBubble.differenceAn', lang),
      right_differences: range(3, 'diagram.doubleBubble.differenceBn', lang),
    },
    tree_map: {
      topic: lt('diagram.defaults.rootTopic', lang),
      dimension: '',
      alternative_dimensions: [],
      children: Array.from({ length: 4 }, (_, ci) => ({
        text: lt('diagram.defaults.categoryN', lang, { n: ci + 1 }),
        children: Array.from({ length: 3 }, (_, ii) => ({
          text: lt('diagram.defaults.itemNM', lang, { n: ci + 1, m: ii + 1 }),
          children: [],
        })),
      })),
    },
    brace_map: {
      whole: lt('diagram.defaults.topic', lang),
      dimension: '',
      parts: Array.from({ length: 3 }, (_, pi) => ({
        name: lt('diagram.defaults.partN', lang, { n: pi + 1 }),
        subparts: Array.from({ length: 2 }, (_, si) => ({
          name: lt('diagram.defaults.subpartNM', lang, { n: pi + 1, m: si + 1 }),
        })),
      })),
    },
    flow_map: {
      title: lt('diagram.defaults.process', lang),
      steps: range(4, 'diagram.defaults.stepN', lang),
      substeps: Array.from({ length: 4 }, (_, si) => ({
        step: lt('diagram.defaults.stepN', lang, { n: si + 1 }),
        substeps: Array.from({ length: 2 }, (_, ssi) =>
          lt('diagram.defaults.substepNM', lang, { n: si + 1, m: ssi + 1 })
        ),
      })),
    },
    multi_flow_map: {
      event: lt('diagram.defaults.mainEvent', lang),
      causes: range(4, 'diagram.defaults.causeN', lang),
      effects: range(4, 'diagram.defaults.effectN', lang),
    },
    bridge_map: {
      relating_factor: lt('diagram.labelNode.clickToSet', lang),
      dimension: '',
      analogies: Array.from({ length: 5 }, (_, i) => ({
        left: lt('diagram.defaults.bridgeItemAN', lang, { n: i + 1 }),
        right: lt('diagram.defaults.bridgeItemBN', lang, { n: i + 1 }),
      })),
      alternative_dimensions: [],
    },
    mindmap: {
      topic: lt('diagram.defaults.centralTopic', lang),
      children: Array.from({ length: 4 }, (_, bi) => ({
        id: `branch_${bi}`,
        label: lt('diagram.defaults.branchN', lang, { n: bi + 1 }),
        text: lt('diagram.defaults.branchN', lang, { n: bi + 1 }),
        children: Array.from({ length: 2 }, (_, ci) => ({
          id: `sub_${bi}_${ci}`,
          label: lt('diagram.defaults.childNM', lang, { n: bi + 1, m: ci + 1 }),
          text: lt('diagram.defaults.childNM', lang, { n: bi + 1, m: ci + 1 }),
          children: [],
        })),
      })),
    },
    concept_map: {
      topic: fq,
      concepts: [],
      relationships: [],
      focus_question: fq,
    },
  }
}

const CACHE = new Map<string, Record<string, Record<string, unknown>>>()

export function getDefaultTemplate(
  diagramType: DiagramType,
  language: LocaleCode
): Record<string, unknown> | null {
  const normalized: DiagramType = diagramType === 'mind_map' ? 'mindmap' : diagramType
  if (!CACHE.has(language)) {
    CACHE.set(language, templatesForLocale(language))
  }
  const table = CACHE.get(language)
  if (table === undefined) {
    return null
  }
  const spec = table[normalized]
  return spec ? { ...spec } : null
}
