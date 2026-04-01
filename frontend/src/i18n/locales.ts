/**
 * UI locale helpers and prompt-registry integration.
 * The locale table lives in `supportedUiLocales.ts` (`SUPPORTED_UI_LOCALES`).
 * When adding a code: edit `supportedUiLocales.ts`, then stub or run `npm run i18n:materialize-from-en`,
 * `elementPlusLocale.ts`, and `scripts/check-i18n-keys.ts` (regenerate `i18n/index.ts` if the script is extended).
 * Translate UI copy by editing values in `src/locales/messages/<code>/*.ts` (same keys as `en/`), e.g. in Cursor/Composer.
 */
import promptLanguageRegistry from '@data/prompt_language_registry.json'

import { SUPPORTED_UI_LOCALES } from './supportedUiLocales'
import type { LocaleCode, UiLocaleEntry } from './supportedUiLocales'

export { SUPPORTED_UI_LOCALES, type LocaleCode, type UiLocaleEntry } from './supportedUiLocales'

/** Enabled UI locales in registry order (for cycling, validation, etc.). */
export const UI_LOCALE_CODES: LocaleCode[] = SUPPORTED_UI_LOCALES.filter((e) => e.enabled).map(
  (e) => e.code
)

/**
 * Locales listed in Settings → Interface language (and mobile account UI picker).
 *
 * Policy: add a code only after all 10 message modules are translated (no materialize stub in any file).
 * See repo docs: `docs/i18n-belt-and-road-master-plan.md` (strategy + locale completion criteria).
 * Guard: `npm run i18n:check-picker-stubs` (from `frontend/`).
 */
export const INTERFACE_LANGUAGE_PICKER_CODES: readonly LocaleCode[] = [
  'zh-tw',
  'zh',
  'en',
  'es',
  'az',
  'th',
  'fr',
  'de',
  'sq',
  'ja',
  'ko',
  'pt',
  'ru',
  'ar',
  'fa',
  'uz',
  'nl',
  'it',
  'hi',
  'id',
  'tl',
  'vi',
  'tr',
  'pl',
  'uk',
  'ms',
  'af',
] as const

/** Locales in Settings → Interface language — use this for “supports {n} languages” next to 界面语言. */
export const INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT = INTERFACE_LANGUAGE_PICKER_CODES.length

const INTERFACE_LANGUAGE_PICKER_SET = new Set<string>(INTERFACE_LANGUAGE_PICKER_CODES)

export function isInterfaceLanguagePickerLocale(code: string): boolean {
  return INTERFACE_LANGUAGE_PICKER_SET.has(code)
}

/**
 * Enabled registry entries shown in the interface-language dropdown.
 * Always includes `currentUiCode` when set so an existing saved locale outside the list still displays.
 */
export function getLocalesForInterfaceLanguagePicker(
  currentUiCode?: string | null
): UiLocaleEntry[] {
  return SUPPORTED_UI_LOCALES.filter((e) => {
    if (!e.enabled) return false
    if (INTERFACE_LANGUAGE_PICKER_SET.has(e.code)) return true
    return currentUiCode != null && e.code === currentUiCode
  }) as UiLocaleEntry[]
}

const UI_LOCALE_SET = new Set<string>(UI_LOCALE_CODES)

export function isUiLocale(value: string | null | undefined): value is LocaleCode {
  return typeof value === 'string' && UI_LOCALE_SET.has(value)
}

const LOCALE_BY_CODE: Record<LocaleCode, UiLocaleEntry> = {} as Record<LocaleCode, UiLocaleEntry>
for (const entry of SUPPORTED_UI_LOCALES) {
  LOCALE_BY_CODE[entry.code] = entry
}

/** Default when browser language does not match any enabled locale. */
export const DEFAULT_UI_LOCALE: LocaleCode = 'en'

export function intlLocaleForUiCode(code: LocaleCode): string {
  return LOCALE_BY_CODE[code]?.intlLocale ?? LOCALE_BY_CODE[DEFAULT_UI_LOCALE].intlLocale
}

export function htmlLangForUiCode(code: LocaleCode): string {
  return LOCALE_BY_CODE[code]?.htmlLang ?? LOCALE_BY_CODE[DEFAULT_UI_LOCALE].htmlLang
}

export function toolbarShortForUiCode(code: LocaleCode): string {
  const short = LOCALE_BY_CODE[code]?.toolbarShort
  return typeof short === 'string' ? short : code.toUpperCase()
}

export function isRtlUiLocale(code: LocaleCode): boolean {
  return LOCALE_BY_CODE[code]?.rtl === true
}

/**
 * Map navigator.language to a supported UI locale (guest / login modal).
 * Matches enabled entries in registry order; falls back to DEFAULT_UI_LOCALE.
 */
export function detectBrowserLocale(): LocaleCode {
  if (typeof navigator === 'undefined') return DEFAULT_UI_LOCALE
  const nav = navigator.language.toLowerCase()
  for (const entry of SUPPORTED_UI_LOCALES) {
    if (!entry.enabled) continue
    const prefixes = entry.browserPrefixes ?? [entry.code]
    for (const p of prefixes) {
      if (nav.startsWith(p.toLowerCase())) {
        return entry.code
      }
    }
  }
  return DEFAULT_UI_LOCALE
}

/** One row from data/prompt_language_registry.json (synced with Python). */
export interface PromptLanguageRegistryEntry {
  code: string
  englishName: string
  nativeLabel: string
  search: string[]
}

/** Generation / prompt output registry (matches utils/prompt_output_languages.py). */
export const PROMPT_LANGUAGE_REGISTRY: PromptLanguageRegistryEntry[] =
  promptLanguageRegistry as PromptLanguageRegistryEntry[]

/** Stable order: zh, zh-hant, en first, then remaining codes alphabetically. */
const _PRIORITY = new Map<string, number>([
  ['zh', 0],
  ['zh-hant', 1],
  ['en', 2],
])

function _registrySort(a: PromptLanguageRegistryEntry, b: PromptLanguageRegistryEntry): number {
  const pa = _PRIORITY.get(a.code) ?? 99
  const pb = _PRIORITY.get(b.code) ?? 99
  if (pa !== pb) return pa - pb
  return a.code.localeCompare(b.code)
}

const _SORTED_REGISTRY = [...PROMPT_LANGUAGE_REGISTRY].sort(_registrySort)

/** All API codes (for validation). */
export const PROMPT_OUTPUT_LANGUAGE_CODES: readonly string[] = _SORTED_REGISTRY.map((e) => e.code)

const _PROMPT_LANG_SET = new Set(PROMPT_OUTPUT_LANGUAGE_CODES)

export function isPromptOutputLanguageCode(value: string | null | undefined): value is string {
  return typeof value === 'string' && _PROMPT_LANG_SET.has(value)
}

/** Any registered generation language code (prefer isPromptOutputLanguageCode for validation). */
export type PromptOutputLanguageCode = string

/** @deprecated Use PROMPT_OUTPUT_LANGUAGE_CODES */
export const PROMPT_LANGUAGE_CODES: readonly string[] = PROMPT_OUTPUT_LANGUAGE_CODES

/** Dropdown rows: API code, native label, English name, search terms for filter. */
export const PROMPT_LANGUAGE_OPTIONS: {
  code: string
  label: string
  englishName: string
  search: string[]
}[] = _SORTED_REGISTRY.map((e) => ({
  code: e.code,
  label: e.nativeLabel,
  englishName: e.englishName,
  search: e.search,
}))
