/**
 * Locale-aware placeholder strings for new diagrams and concept map edge/topic logic.
 */
import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { UI_LOCALE_CODES } from '@/i18n/locales'

function conceptT(key: string, lang: LocaleCode): string {
  return String(i18n.global.t(key, {}, { locale: lang }))
}

export function defaultUiLocaleGroup(lang: LocaleCode): 'zh' | 'en' {
  return lang === 'zh' ? 'zh' : 'en'
}

export function getConceptMapFocusQuestionPrefix(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.focusQuestionPrefix', lang)
}

export function getConceptMapFocusQuestionSuffix(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.focusQuestionSuffix', lang)
}

export function getConceptMapFocusQuestionDefault(lang: LocaleCode): string {
  return getConceptMapFocusQuestionPrefix(lang) + getConceptMapFocusQuestionSuffix(lang)
}

export function getConceptMapRootConceptText(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.rootConcept', lang)
}

/** Edge label for topic → default root concept (mirrors 的根概念). */
export function getConceptMapTopicRootRelationshipLabel(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.topicRootRelationship', lang)
}

/** Known labels for the topic → root edge (saved diagrams may use any UI locale). */
export const ALL_TOPIC_ROOT_RELATIONSHIP_LABELS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapTopicRootRelationshipLabel(l)
)

/** Known default root concept node texts. */
export const ALL_ROOT_CONCEPT_NODE_TEXTS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapRootConceptText(l)
)

/** Default focus question topic strings (for muted styling). */
export const ALL_FOCUS_QUESTION_DEFAULTS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapFocusQuestionDefault(l)
)

export function stripConceptMapFocusQuestionPrefix(raw: string): string {
  const trimmed = raw.trim()
  for (const loc of UI_LOCALE_CODES) {
    const prefix = getConceptMapFocusQuestionPrefix(loc)
    if (trimmed.startsWith(prefix)) {
      return trimmed.slice(prefix.length).trim()
    }
  }
  return trimmed
}

export function isDefaultFocusQuestionLabel(label: string): boolean {
  return ALL_FOCUS_QUESTION_DEFAULTS.includes(label.trim())
}

export function focusQuestionMutedParts(label: string): { prefix: string; suffix: string } | null {
  const t = label.trim()
  for (const loc of UI_LOCALE_CODES) {
    const def = getConceptMapFocusQuestionDefault(loc)
    if (t === def) {
      return {
        prefix: getConceptMapFocusQuestionPrefix(loc),
        suffix: getConceptMapFocusQuestionSuffix(loc),
      }
    }
  }
  return null
}
