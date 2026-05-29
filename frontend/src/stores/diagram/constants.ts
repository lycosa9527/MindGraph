import type { LocaleCode } from '@/i18n/locales'
import { UI_LOCALE_CODES } from '@/i18n/locales'
import { isLocaleLoaded } from '@/i18n'
import { registerLocaleLabelCacheInvalidator } from '@/i18n/localeLabelCache'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
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

function localesForLabelCache(): LocaleCode[] {
  return UI_LOCALE_CODES.filter((loc) => isLocaleLoaded(loc))
}

function placeholderStringsForLocales(fn: (lang: LocaleCode) => string): string[] {
  return localesForLabelCache().map(fn)
}

function i18nPlaceholdersForAllLocales(key: string): string[] {
  return localesForLabelCache().map((lang) => translateForUiLocale(key, lang))
}

let cachedPlaceholderTexts: readonly string[] | null = null

function buildPlaceholderTexts(): readonly string[] {
  return [
    ...new Set([
      ...i18nPlaceholdersForAllLocales('diagram.defaults.topic'),
      ...i18nPlaceholdersForAllLocales('diagram.defaults.centralTopic'),
      ...i18nPlaceholdersForAllLocales('diagram.defaults.rootTopic'),
      ...i18nPlaceholdersForAllLocales('diagram.defaults.mainEvent'),
      ...placeholderStringsForLocales(getConceptMapFocusQuestionDefault),
      ...placeholderStringsForLocales(getConceptMapRootConceptText),
    ]),
  ]
}

export function getPlaceholderTexts(): readonly string[] {
  if (cachedPlaceholderTexts === null) {
    cachedPlaceholderTexts = buildPlaceholderTexts()
  }
  return cachedPlaceholderTexts
}

function invalidatePlaceholderTextsCache(): void {
  cachedPlaceholderTexts = null
}

registerLocaleLabelCacheInvalidator(invalidatePlaceholderTextsCache)
