import { createI18n } from 'vue-i18n'

import afMessages from '@/locales/messages/af'
import amMessages from '@/locales/messages/am'
import arMessages from '@/locales/messages/ar'
import azMessages from '@/locales/messages/az'
import bgMessages from '@/locales/messages/bg'
import bnMessages from '@/locales/messages/bn'
import caMessages from '@/locales/messages/ca'
import csMessages from '@/locales/messages/cs'
import daMessages from '@/locales/messages/da'
import deMessages from '@/locales/messages/de'
import elMessages from '@/locales/messages/el'
import enMessages from '@/locales/messages/en'
import esMessages from '@/locales/messages/es'
import faMessages from '@/locales/messages/fa'
import fiMessages from '@/locales/messages/fi'
import frMessages from '@/locales/messages/fr'
import haMessages from '@/locales/messages/ha'
import heMessages from '@/locales/messages/he'
import hiMessages from '@/locales/messages/hi'
import hrMessages from '@/locales/messages/hr'
import huMessages from '@/locales/messages/hu'
import hyMessages from '@/locales/messages/hy'
import idMessages from '@/locales/messages/id'
import igMessages from '@/locales/messages/ig'
import itMessages from '@/locales/messages/it'
import jaMessages from '@/locales/messages/ja'
import kaMessages from '@/locales/messages/ka'
import kkMessages from '@/locales/messages/kk'
import kmMessages from '@/locales/messages/km'
import koMessages from '@/locales/messages/ko'
import kyMessages from '@/locales/messages/ky'
import loMessages from '@/locales/messages/lo'
import mnMessages from '@/locales/messages/mn'
import msMessages from '@/locales/messages/ms'
import myMessages from '@/locales/messages/my'
import neMessages from '@/locales/messages/ne'
import nlMessages from '@/locales/messages/nl'
import noMessages from '@/locales/messages/no'
import plMessages from '@/locales/messages/pl'
import ptMessages from '@/locales/messages/pt'
import roMessages from '@/locales/messages/ro'
import ruMessages from '@/locales/messages/ru'
import siMessages from '@/locales/messages/si'
import soMessages from '@/locales/messages/so'
import srMessages from '@/locales/messages/sr'
import ssMessages from '@/locales/messages/ss'
import stMessages from '@/locales/messages/st'
import svMessages from '@/locales/messages/sv'
import swMessages from '@/locales/messages/sw'
import taMessages from '@/locales/messages/ta'
import tgMessages from '@/locales/messages/tg'
import thMessages from '@/locales/messages/th'
import tkMessages from '@/locales/messages/tk'
import tlMessages from '@/locales/messages/tl'
import tnMessages from '@/locales/messages/tn'
import trMessages from '@/locales/messages/tr'
import ugMessages from '@/locales/messages/ug'
import ukMessages from '@/locales/messages/uk'
import urMessages from '@/locales/messages/ur'
import uzMessages from '@/locales/messages/uz'
import viMessages from '@/locales/messages/vi'
import xhMessages from '@/locales/messages/xh'
import yoMessages from '@/locales/messages/yo'
import zhMessages from '@/locales/messages/zh'
import zhTwMessages from '@/locales/messages/zh-tw'
import zuMessages from '@/locales/messages/zu'

import type { LocaleCode } from './locales'
import { SUPPORTED_UI_LOCALES, htmlLangForUiCode } from './locales'

export type { LocaleCode } from './locales'
export { intlLocaleForUiCode } from './locales'
export type { MessageSchema } from './messageSchema'
export { loadElementPlusLocale } from './elementPlusLocale'

const EN_FLAT = enMessages as Record<string, string>

/**
 * All UI locales registered for vue-i18n.
 * Bundles cloned from English use the same keys until translated.
 */
const ALL_UI_MESSAGES: { [K in LocaleCode]: Record<string, string> } = {
  af: afMessages as Record<string, string>,
  am: amMessages as Record<string, string>,
  ar: arMessages as Record<string, string>,
  az: azMessages as Record<string, string>,
  bg: bgMessages as Record<string, string>,
  bn: bnMessages as Record<string, string>,
  ca: caMessages as Record<string, string>,
  cs: csMessages as Record<string, string>,
  da: daMessages as Record<string, string>,
  de: deMessages as Record<string, string>,
  el: elMessages as Record<string, string>,
  en: EN_FLAT,
  es: esMessages as Record<string, string>,
  fa: faMessages as Record<string, string>,
  fi: fiMessages as Record<string, string>,
  fr: frMessages as Record<string, string>,
  ha: haMessages as Record<string, string>,
  he: heMessages as Record<string, string>,
  hi: hiMessages as Record<string, string>,
  hr: hrMessages as Record<string, string>,
  hu: huMessages as Record<string, string>,
  hy: hyMessages as Record<string, string>,
  id: idMessages as Record<string, string>,
  ig: igMessages as Record<string, string>,
  it: itMessages as Record<string, string>,
  ja: jaMessages as Record<string, string>,
  ka: kaMessages as Record<string, string>,
  kk: kkMessages as Record<string, string>,
  km: kmMessages as Record<string, string>,
  ko: koMessages as Record<string, string>,
  ky: kyMessages as Record<string, string>,
  lo: loMessages as Record<string, string>,
  mn: mnMessages as Record<string, string>,
  ms: msMessages as Record<string, string>,
  my: myMessages as Record<string, string>,
  ne: neMessages as Record<string, string>,
  nl: nlMessages as Record<string, string>,
  no: noMessages as Record<string, string>,
  pl: plMessages as Record<string, string>,
  pt: ptMessages as Record<string, string>,
  ro: roMessages as Record<string, string>,
  ru: ruMessages as Record<string, string>,
  si: siMessages as Record<string, string>,
  so: soMessages as Record<string, string>,
  sr: srMessages as Record<string, string>,
  ss: ssMessages as Record<string, string>,
  st: stMessages as Record<string, string>,
  sv: svMessages as Record<string, string>,
  sw: swMessages as Record<string, string>,
  ta: taMessages as Record<string, string>,
  tg: tgMessages as Record<string, string>,
  th: thMessages as Record<string, string>,
  tk: tkMessages as Record<string, string>,
  tl: tlMessages as Record<string, string>,
  tn: tnMessages as Record<string, string>,
  tr: trMessages as Record<string, string>,
  ug: ugMessages as Record<string, string>,
  uk: ukMessages as Record<string, string>,
  ur: urMessages as Record<string, string>,
  uz: uzMessages as Record<string, string>,
  vi: viMessages as Record<string, string>,
  xh: xhMessages as Record<string, string>,
  yo: yoMessages as Record<string, string>,
  zh: zhMessages as Record<string, string>,
  'zh-tw': zhTwMessages as Record<string, string>,
  zu: zuMessages as Record<string, string>,
}

/** Typed keys for `t()` — use `import type { MessageSchema } from '@/i18n/messageSchema'`. */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: ALL_UI_MESSAGES,
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

const loadedLocales = new Set<LocaleCode>(SUPPORTED_UI_LOCALES.map((e) => e.code) as LocaleCode[])

export async function loadLocaleMessages(locale: LocaleCode): Promise<void> {
  if (loadedLocales.has(locale)) return
  const mod = await import(`../locales/messages/${locale}.ts`)
  i18n.global.setLocaleMessage(locale, mod.default as Record<string, string>)
  loadedLocales.add(locale)
}

export function setI18nLocale(locale: LocaleCode): void {
  const loc = i18n.global.locale as { value: LocaleCode }
  loc.value = locale
}

/** BCP 47–friendly value for the document element. */
export function htmlLangForLocale(locale: LocaleCode): string {
  return htmlLangForUiCode(locale)
}
