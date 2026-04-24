import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { UI_LOCALE_CODES } from '@/i18n/locales'
import {
  getConceptMapFocusQuestionDefault,
  getConceptMapRootConceptText,
} from '@/stores/diagram/diagramDefaultLabels'
import type { DiagramType } from '@/types'

export const VALID_DIAGRAM_TYPES: DiagramType[] = [
  'bubble_map',
  'bridge_map',
  'tree_map',
  'circle_map',
  'double_bubble_map',
  'flow_map',
  'brace_map',
  'multi_flow_map',
  'concept_map',
  'mindmap',
  'mind_map',
  'diagram',
]

export const MAX_HISTORY_SIZE = 50

function placeholderStringsForLocales(fn: (lang: LocaleCode) => string): string[] {
  return UI_LOCALE_CODES.map(fn)
}

function i18nPlaceholdersForAllLocales(key: string): string[] {
  return UI_LOCALE_CODES.map((lang) => String(i18n.global.t(key, {}, { locale: lang as any })))
}

export const PLACEHOLDER_TEXTS = [
  ...new Set([
    ...i18nPlaceholdersForAllLocales('diagram.defaults.topic'),
    ...i18nPlaceholdersForAllLocales('diagram.defaults.centralTopic'),
    ...i18nPlaceholdersForAllLocales('diagram.defaults.rootTopic'),
    ...i18nPlaceholdersForAllLocales('diagram.defaults.mainEvent'),
    ...placeholderStringsForLocales(getConceptMapFocusQuestionDefault),
    ...placeholderStringsForLocales(getConceptMapRootConceptText),
  ]),
]
