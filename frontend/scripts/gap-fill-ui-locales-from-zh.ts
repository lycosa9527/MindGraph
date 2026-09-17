/**
 * Gap-fill UI locales from Simplified Chinese.
 * Keys still equal to English are translated zh-CN → target. English is fill only
 * when zh is missing, the value is language-independent, or Google fails.
 *
 * Windows host only (VPN / system proxy). WSL cannot reach Google.
 *
 *   node scripts/gap-fill-ui-locales-from-zh.ts --dry-run
 *   node scripts/gap-fill-ui-locales-from-zh.ts --locale=ar,pt,ru,fa
 *   node scripts/gap-fill-ui-locales-from-zh.ts --all-enabled
 */
import { existsSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import translate from 'google-translate-api-x'

import {
  htmlLangForUiCode,
  INTERFACE_LANGUAGE_PICKER_CODES,
  UI_LOCALE_CODES,
  type LocaleCode,
} from '../src/i18n/locales.ts'
import { localeNamespaceBanner } from './i18nFileBanner.ts'
import { setupFetchProxy } from './setup-fetch-proxy.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')

const NS_FILES = [
  'common',
  'mindmate',
  'maite',
  'canvas',
  'workshop',
  'training',
  'admin',
  'knowledge',
  'community',
  'showcase',
  'zhihui',
  'sidebar',
  'auth',
  'notification',
  'thinkingCoins',
] as const

type Namespace = (typeof NS_FILES)[number]

const SKIP_LOCALES = new Set<string>(['en', 'zh', 'zh-tw'])
const TIER_A = ['ar', 'pt', 'ru', 'fa'] as const
const KEEP_VALUES = new Set([
  'Mind Platform',
  'MindGraph',
  'MindMate',
  'MindBot',
  'TEST',
  'www.mindspringedu.com',
])
const BARE_KEY_COMBO = /^(Ctrl|Shift|Alt|⌘)\+[A-Za-z0-9]+$/i
const BARE_VERSION = /^V\d+$/i
const PLACEHOLDER_RE = /\{[^}]+\}/g

function pickerLocaleOrder(): LocaleCode[] {
  const rest = INTERFACE_LANGUAGE_PICKER_CODES.filter(
    (code) => !SKIP_LOCALES.has(code) && !TIER_A.includes(code as (typeof TIER_A)[number])
  )
  return [...TIER_A, ...rest] as LocaleCode[]
}

function allEnabledLocaleOrder(): LocaleCode[] {
  const picker = new Set<string>(pickerLocaleOrder())
  const rest = UI_LOCALE_CODES.filter((code) => !SKIP_LOCALES.has(code) && !picker.has(code))
  return [...pickerLocaleOrder(), ...rest]
}

function parseArgs(): {
  locales: LocaleCode[]
  dryRun: boolean
  onlyNs: Set<Namespace> | null
} {
  const dryRun = process.argv.includes('--dry-run')
  const allEnabled = process.argv.includes('--all-enabled')
  const locArg = process.argv.find((a) => a.startsWith('--locale='))
  const onlyArg = process.argv.find((a) => a.startsWith('--only-ns='))
  let locales = allEnabled ? allEnabledLocaleOrder() : pickerLocaleOrder()
  if (locArg !== undefined) {
    locales = locArg
      .slice('--locale='.length)
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !SKIP_LOCALES.has(s)) as LocaleCode[]
  }
  let onlyNs: Set<Namespace> | null = null
  if (onlyArg !== undefined) {
    onlyNs = new Set(
      onlyArg
        .slice('--only-ns='.length)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean) as Namespace[]
    )
  }
  return { locales, dryRun, onlyNs }
}

function googleToForLocale(code: string, htmlLang: string): string {
  const h = htmlLang.toLowerCase()
  if (h === 'fil' || code === 'tl') {
    return 'tl'
  }
  if (code === 'pt') {
    return 'pt'
  }
  const seg = htmlLang.split('-')[0]
  if (seg.toLowerCase() === 'fil') {
    return 'tl'
  }
  return seg
}

function isKeepFill(value: string): boolean {
  const v = value.trim()
  if (v.length === 0) {
    return true
  }
  if (KEEP_VALUES.has(v)) {
    return true
  }
  const withoutSlots = v.replace(PLACEHOLDER_RE, '').trim()
  if (withoutSlots.length === 0 || !/\p{L}/u.test(withoutSlots)) {
    return true
  }
  if (!/\p{L}/u.test(v)) {
    return true
  }
  return BARE_KEY_COMBO.test(v) || BARE_VERSION.test(v)
}

function escapeSq(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r\n/g, '\n').replace(/\n/g, '\\n')
}

function formatRecord(keysInOrder: string[], out: Record<string, string>): string {
  const lines = keysInOrder.map((k) => `  '${escapeSq(k)}': '${escapeSq(out[k])}',`)
  return `{\n${lines.join('\n')}\n}`
}

function formatNamespaceExport(
  ns: Namespace,
  keysInOrder: string[],
  out: Record<string, string>
): string {
  const formatted = formatRecord(keysInOrder, out)
  if (ns === 'thinkingCoins') {
    return `export const thinkingCoinsMessages = ${formatted} as const\n`
  }
  return `export default ${formatted} as const\n`
}

async function loadMod(locale: string, ns: Namespace): Promise<Record<string, string>> {
  const abs = join(ROOT, locale, `${ns}.ts`)
  if (!existsSync(abs)) {
    return {}
  }
  const url = `${pathToFileURL(abs).href}?t=${Date.now()}&l=${locale}&n=${ns}`
  const mod = (await import(url)) as Record<string, unknown>
  if (ns === 'thinkingCoins') {
    const d = mod.thinkingCoinsMessages
    return typeof d === 'object' && d !== null ? (d as Record<string, string>) : {}
  }
  const d = mod.default
  return typeof d === 'object' && d !== null ? (d as Record<string, string>) : {}
}

function protectPlaceholders(s: string): { text: string; tokens: string[] } {
  const tokens: string[] = []
  let i = 0
  const text = s.replace(PLACEHOLDER_RE, (m) => {
    tokens.push(m)
    return `__MG_${i++}__`
  })
  return { text, tokens }
}

function restorePlaceholders(s: string, tokens: string[]): string {
  let out = s
  for (let i = 0; i < tokens.length; i++) {
    out = out.replace(`__MG_${i}__`, tokens[i])
  }
  return out
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => {
    setTimeout(r, ms)
  })
}

async function translateBatch(texts: string[], to: string): Promise<string[]> {
  if (texts.length === 0) {
    return []
  }
  const prepared = texts.map((t) => protectPlaceholders(t))
  const chunkSize = 40
  const out: string[] = []
  for (let c = 0; c < prepared.length; c += chunkSize) {
    const slice = prepared.slice(c, c + chunkSize)
    const inputs = slice.map((p) => p.text)
    let attempt = 0
    let ok = false
    let lastErr: unknown = null
    while (attempt < 5 && !ok) {
      try {
        const res = await translate(inputs, {
          from: 'zh-CN',
          to,
          forceTo: true,
          forceBatch: true,
        })
        const arr = Array.isArray(res) ? res : [res]
        for (let i = 0; i < slice.length; i++) {
          const raw = (arr[i] as { text?: string } | undefined)?.text ?? ''
          out.push(restorePlaceholders(raw, slice[i].tokens))
        }
        ok = true
      } catch (err) {
        lastErr = err
        attempt += 1
        await sleep(800 * attempt)
      }
    }
    if (!ok) {
      console.error(`batch failed (${to}) at ${c}`, lastErr)
      for (let i = 0; i < slice.length; i++) {
        out.push('')
      }
    }
    await sleep(120)
  }
  return out
}

function writeNamespace(
  locale: string,
  ns: Namespace,
  keys: string[],
  out: Record<string, string>
): void {
  const body = formatNamespaceExport(ns, keys, out)
  const next = `${localeNamespaceBanner(locale, ns)}\n${body}`
  writeFileSync(join(ROOT, locale, `${ns}.ts`), next, 'utf8')
}

interface GapRow {
  key: string
  zhText: string
}

function collectGaps(
  loc: Record<string, string>,
  en: Record<string, string>,
  zh: Record<string, string>
): { out: Record<string, string>; gaps: GapRow[] } {
  const keys = Object.keys(loc)
  const out: Record<string, string> = { ...loc }
  const gaps: GapRow[] = []
  for (const key of keys) {
    const enVal = en[key]
    if (enVal === undefined || loc[key] !== enVal) {
      continue
    }
    if (isKeepFill(enVal)) {
      continue
    }
    const zhText = zh[key]
    if (zhText === undefined || zhText.length === 0) {
      continue
    }
    gaps.push({ key, zhText })
  }
  return { out, gaps }
}

async function fillNamespace(
  locale: LocaleCode,
  ns: Namespace,
  to: string,
  dryRun: boolean
): Promise<{ gap: number; kept: number; failed: number; sample: string | null }> {
  const loc = await loadMod(locale, ns)
  const en = await loadMod('en', ns)
  const zh = await loadMod('zh', ns)
  const keys = Object.keys(loc)
  if (keys.length === 0) {
    return { gap: 0, kept: 0, failed: 0, sample: null }
  }
  const { out, gaps } = collectGaps(loc, en, zh)
  const sample = gaps[0]?.zhText ?? null
  if (dryRun || gaps.length === 0) {
    return { gap: gaps.length, kept: 0, failed: 0, sample }
  }
  const translated = await translateBatch(
    gaps.map((g) => g.zhText),
    to
  )
  let failed = 0
  let kept = 0
  for (let i = 0; i < gaps.length; i++) {
    const { key } = gaps[i]
    const next = translated[i]
    if (typeof next === 'string' && next.trim().length > 0) {
      out[key] = next
      kept += 1
    } else {
      failed += 1
    }
  }
  writeNamespace(locale, ns, keys, out)
  return { gap: gaps.length, kept, failed, sample }
}

async function main(): Promise<void> {
  const { locales, dryRun, onlyNs } = parseArgs()
  const nsList = NS_FILES.filter((ns) => onlyNs === null || onlyNs.has(ns))
  if (locales.length === 0 || nsList.length === 0) {
    console.error('No locales or namespaces to process.')
    process.exit(1)
  }

  if (!dryRun) {
    setupFetchProxy(process.argv)
  }

  console.log(
    dryRun ? 'DRY RUN (no Google)' : 'Translating zh-CN → target locales',
    locales.join(','),
    '| ns:',
    nsList.join(',')
  )

  let totalGap = 0
  let totalFailed = 0
  for (const locale of locales) {
    const to = googleToForLocale(locale, htmlLangForUiCode(locale))
    let locGap = 0
    let locFailed = 0
    let sample: string | null = null
    for (const ns of nsList) {
      const row = await fillNamespace(locale, ns, to, dryRun)
      locGap += row.gap
      locFailed += row.failed
      if (sample === null && row.sample !== null) {
        sample = row.sample
      }
      if (!dryRun && row.gap > 0) {
        console.log(`  ${locale}/${ns}: filled ${row.kept}/${row.gap} failed ${row.failed}`)
      }
    }
    totalGap += locGap
    totalFailed += locFailed
    console.log(`${locale} -> ${to}: gap ${locGap} failed ${locFailed} sample=${sample ?? ''}`)
  }
  console.log(`done. gap=${totalGap} failed=${totalFailed}`)
}

main().catch((err: unknown) => {
  console.error(err)
  process.exit(1)
})
