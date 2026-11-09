/**
 * Labels for a node the user inserts. A bilingual diagram gets the catalog
 * label in both file languages, so the new node shows two lines like the rest.
 */
import { i18n, isLocaleLoaded, loadLocaleMessages } from '@/i18n'
import { type LocaleCode, uiLocaleForPromptLanguage } from '@/i18n/locales'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'

import { readDiagramLanguages } from './mirror'

export interface InsertLabel {
  text: string
  textSecondary?: string
}

/** A plain string is a primary-only label (AI, voice, and paste text). */
export type InsertLabelInput = string | InsertLabel

export function insertLabelText(label: InsertLabelInput): string {
  return typeof label === 'string' ? label : label.text
}

export function insertLabelGloss(label: InsertLabelInput): string {
  return typeof label === 'string' ? '' : (label.textSecondary ?? '').trim()
}

/** `{ text }` plus `textSecondary` only when there is a gloss. */
export function insertLabelFields(label: InsertLabelInput): InsertLabel {
  const text = insertLabelText(label)
  const gloss = insertLabelGloss(label)
  return gloss ? { text, textSecondary: gloss } : { text }
}

/** Apply the same suffix to both lines (`New Child 1`). */
export function suffixInsertLabel(label: InsertLabelInput, suffix: string): InsertLabel {
  const gloss = insertLabelGloss(label)
  const text = `${insertLabelText(label)}${suffix}`
  return gloss ? { text, textSecondary: `${gloss}${suffix}` } : { text }
}

/** Apply `transform` to both lines. */
export function mapInsertLabel(
  label: InsertLabelInput,
  transform: (line: string) => string
): InsertLabel {
  const gloss = insertLabelGloss(label)
  const text = transform(insertLabelText(label))
  return gloss ? { text, textSecondary: transform(gloss) } : { text }
}

function fileLocales(languages: unknown): { primary: LocaleCode; secondary: LocaleCode } | null {
  const pair = readDiagramLanguages({ languages })
  if (!pair) return null
  const primary = uiLocaleForPromptLanguage(pair.primary)
  const secondary = uiLocaleForPromptLanguage(pair.secondary)
  if (!primary || !secondary || primary === secondary) return null
  return { primary, secondary }
}

/** Start loading both file-language catalogs so the first insert has its gloss. */
export function preloadDiagramLanguageCatalogs(languages: unknown): void {
  const locales = fileLocales(languages)
  if (!locales) return
  for (const locale of [locales.primary, locales.secondary]) {
    if (!isLocaleLoaded(locale)) void loadLocaleMessages(locale).catch(() => undefined)
  }
}

/**
 * Catalog label for an inserted node. A single-language diagram uses the
 * interface language. A bilingual diagram uses its file pair instead.
 */
export function diagramInsertLabel(
  languages: unknown,
  key: string,
  params?: Record<string, unknown>
): InsertLabel {
  const uiText = String(i18n.global.t(key, params ?? {}))
  const locales = fileLocales(languages)
  if (!locales) return { text: uiText }
  preloadDiagramLanguageCatalogs(languages)
  const text = isLocaleLoaded(locales.primary)
    ? translateForUiLocale(key, locales.primary, params)
    : uiText
  if (!isLocaleLoaded(locales.secondary)) return { text }
  const gloss = translateForUiLocale(key, locales.secondary, params).trim()
  return gloss && gloss !== text ? { text, textSecondary: gloss } : { text }
}
