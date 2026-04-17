/**
 * Translate `src/locales/messages/<locale>/*.ts` from English using Google Translate (unofficial API).
 * Prefer hand-written locale files when quality matters; this is a bulk fallback.
 * Preserves `{placeholder}` tokens. Skips: en (source), es (hand-translated), zh, zh-tw.
 *
 * Usage (from frontend/):
 *   npx tsx scripts/translate-ui-locales-from-en.ts
 *   npx tsx scripts/translate-ui-locales-from-en.ts --locale=de
 *   npx tsx scripts/translate-ui-locales-from-en.ts --locale=de,fr,ja
 *   npx tsx scripts/translate-ui-locales-from-en.ts --dry-run
 *   npx tsx scripts/translate-ui-locales-from-en.ts --skip-ns=notification
 *   npx tsx scripts/translate-ui-locales-from-en.ts --only-ns=sidebar,common,auth
 *
 * Proxy (VPN): uses system proxy on Windows (registry) or `HTTPS_PROXY` / `HTTP_PROXY`.
 * Override: `--proxy=http://127.0.0.1:7890`
 */
import translate from 'google-translate-api-x'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import type { LocaleCode } from '../src/i18n/locales'
import { SUPPORTED_UI_LOCALES } from '../src/i18n/supportedUiLocales'
import adminEn from '../src/locales/messages/en/admin'
import authEn from '../src/locales/messages/en/auth'
import canvasEn from '../src/locales/messages/en/canvas'
import commonEn from '../src/locales/messages/en/common'
import communityEn from '../src/locales/messages/en/community'
import knowledgeEn from '../src/locales/messages/en/knowledge'
import mindmateEn from '../src/locales/messages/en/mindmate'
import notificationEn from '../src/locales/messages/en/notification'
import sidebarEn from '../src/locales/messages/en/sidebar'
import workshopEn from '../src/locales/messages/en/workshop'
import { setupFetchProxy } from './setup-fetch-proxy'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')

const SKIP_LOCALES = new Set<LocaleCode>(['en', 'es', 'zh', 'zh-tw'])

const NS_FILES = [
  'admin',
  'auth',
  'canvas',
  'common',
  'community',
  'knowledge',
  'mindmate',
  'notification',
  'sidebar',
  'workshop',
] as const

const EN_BY_NS: Record<(typeof NS_FILES)[number], Record<string, string>> = {
  admin: adminEn as Record<string, string>,
  auth: authEn as Record<string, string>,
  canvas: canvasEn as Record<string, string>,
  common: commonEn as Record<string, string>,
  community: communityEn as Record<string, string>,
  knowledge: knowledgeEn as Record<string, string>,
  mindmate: mindmateEn as Record<string, string>,
  notification: notificationEn as Record<string, string>,
  sidebar: sidebarEn as Record<string, string>,
  workshop: workshopEn as Record<string, string>,
}

const PLACEHOLDER_RE = /\{[^}]+\}/g

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

/** Google Translate `to` code (see google-translate-api-x languages). */
function googleToForLocale(code: string, htmlLang: string): string {
  const h = htmlLang.toLowerCase()
  if (h === 'fil') return 'tl'
  if (h === 'he') return 'iw'
  if (code === 'no') return 'no'
  if (code === 'pt') return 'pt'
  if (code === 'tl') return 'tl'
  const seg = htmlLang.split('-')[0]
  if (seg.toLowerCase() === 'fil') return 'tl'
  return seg
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms))
}

async function translateBatch(texts: string[], to: string, dryRun: boolean): Promise<string[]> {
  if (texts.length === 0) return []
  if (dryRun) return [...texts]

  const prepared = texts.map((t) => protectPlaceholders(t))
  const chunkSize = 45
  const out: string[] = []

  for (let c = 0; c < prepared.length; c += chunkSize) {
    const slice = prepared.slice(c, c + chunkSize)
    const inputs = slice.map((p) => p.text)
    let attempt = 0
    let lastErr: unknown = null
    let ok = false
    while (attempt < 5 && !ok) {
      try {
        const res = await translate(inputs, {
          from: 'en',
          to,
          forceTo: true,
          forceBatch: true,
        })
        const arr = Array.isArray(res) ? res : [res]
        for (let i = 0; i < slice.length; i++) {
          const r = arr[i] as { text: string }
          const raw = r?.text ?? ''
          out.push(restorePlaceholders(raw, slice[i].tokens))
        }
        ok = true
      } catch (e) {
        lastErr = e
        attempt++
        await sleep(800 * attempt)
      }
    }
    if (!ok) {
      console.error('Batch failed, using English for chunk starting', c, lastErr)
      for (let i = 0; i < slice.length; i++) {
        out.push(texts[c + i])
      }
    }
    await sleep(120)
  }

  return out
}

function writeNamespaceFile(
  localeCode: string,
  ns: (typeof NS_FILES)[number],
  entries: Record<string, string>
): void {
  const dir = join(ROOT, localeCode)
  mkdirSync(dir, { recursive: true })
  const title =
    ns === 'canvas'
      ? 'canvas'
      : ns === 'mindmate'
        ? 'mindmate'
        : ns === 'notification'
          ? 'notification'
          : ns
  const header = `/** ${localeCode} UI — ${title} (machine-translated from en; review as needed) */`
  const lines: string[] = [header, 'export default {']
  for (const [k, v] of Object.entries(entries)) {
    lines.push(`  ${JSON.stringify(k)}: ${JSON.stringify(v)},`)
  }
  lines.push('} as const', '')
  writeFileSync(join(dir, `${ns}.ts`), lines.join('\n'), 'utf8')
}

function writeIndexTs(localeCode: string): void {
  const raw = `/**
 * ${localeCode} UI messages — merged namespace bundles.
 */
import admin from './admin'
import auth from './auth'
import canvas from './canvas'
import common from './common'
import community from './community'
import knowledge from './knowledge'
import mindmate from './mindmate'
import notification from './notification'
import sidebar from './sidebar'
import workshop from './workshop'

export default {
  ...common,
  ...mindmate,
  ...canvas,
  ...workshop,
  ...admin,
  ...knowledge,
  ...community,
  ...sidebar,
  ...auth,
  ...notification,
} as const
`
  writeFileSync(join(ROOT, localeCode, 'index.ts'), raw, 'utf8')
}

function writeRootReexport(localeCode: string): void {
  const raw = `/**
 * ${localeCode} UI messages — re-export merged bundles.
 */
export { default } from './${localeCode}/index'
`
  writeFileSync(join(ROOT, `${localeCode}.ts`), raw, 'utf8')
}

function parseArgs(): {
  locales: LocaleCode[] | null
  dryRun: boolean
  skipNs: Set<string>
  onlyNs: Set<string> | null
} {
  const dryRun = process.argv.includes('--dry-run')
  const locArg = process.argv.find((a) => a.startsWith('--locale='))
  const skipArg = process.argv.find((a) => a.startsWith('--skip-ns='))
  const onlyArg = process.argv.find((a) => a.startsWith('--only-ns='))
  const locales = locArg
    ? (locArg
        .slice('--locale='.length)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean) as LocaleCode[])
    : null
  const skipNs = new Set(
    skipArg
      ? skipArg
          .slice('--skip-ns='.length)
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : []
  )
  const onlyNs = onlyArg
    ? new Set(
        onlyArg
          .slice('--only-ns='.length)
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      )
    : null
  return { locales, dryRun, skipNs, onlyNs }
}

function namespacesToProcess(
  skipNs: Set<string>,
  onlyNs: Set<string> | null
): (typeof NS_FILES)[number][] {
  const list: (typeof NS_FILES)[number][] = []
  for (const ns of NS_FILES) {
    if (onlyNs !== null && !onlyNs.has(ns)) {
      continue
    }
    if (skipNs.has(ns)) {
      continue
    }
    list.push(ns)
  }
  return list
}

async function translateLocale(
  localeCode: LocaleCode,
  googleTo: string,
  dryRun: boolean,
  nsToRun: (typeof NS_FILES)[number][]
): Promise<void> {
  console.log(`\n=== ${localeCode} -> ${googleTo} ===`)
  if (dryRun) {
    let n = 0
    for (const ns of nsToRun) {
      n += Object.keys(EN_BY_NS[ns]).length
    }
    console.log(
      `  (dry-run: would write ${n} keys across ${nsToRun.length} namespace(s): ${nsToRun.join(', ')})`
    )
    return
  }
  for (const ns of nsToRun) {
    const enFlat = EN_BY_NS[ns]
    const keys = Object.keys(enFlat)
    const values = keys.map((k) => enFlat[k])
    const translated = await translateBatch(values, googleTo, dryRun)
    const out: Record<string, string> = {}
    for (let i = 0; i < keys.length; i++) {
      out[keys[i]] = translated[i] ?? values[i]
    }
    writeNamespaceFile(localeCode, ns, out)
    console.log(`  ${ns}.ts (${keys.length} keys)`)
  }
  writeIndexTs(localeCode)
  writeRootReexport(localeCode)
}

async function main(): Promise<void> {
  const { locales: only, dryRun, skipNs, onlyNs } = parseArgs()
  if (onlyNs !== null) {
    for (const n of onlyNs) {
      if (!NS_FILES.includes(n as (typeof NS_FILES)[number])) {
        console.error(
          `Unknown namespace in --only-ns: ${n}. Expected one of: ${NS_FILES.join(', ')}`
        )
        process.exit(1)
      }
    }
  }
  for (const n of skipNs) {
    if (!NS_FILES.includes(n as (typeof NS_FILES)[number])) {
      console.error(`Unknown namespace in --skip-ns: ${n}. Expected one of: ${NS_FILES.join(', ')}`)
      process.exit(1)
    }
  }

  const nsToRun = namespacesToProcess(skipNs, onlyNs)
  if (nsToRun.length === 0) {
    console.error('No namespaces to process (--only-ns / --skip-ns left nothing to translate).')
    process.exit(1)
  }

  if (!dryRun) {
    setupFetchProxy()
  }
  const targets = SUPPORTED_UI_LOCALES.filter((e) => {
    if (SKIP_LOCALES.has(e.code)) return false
    if (only && !only.includes(e.code)) return false
    return true
  })

  if (targets.length === 0) {
    console.error('No locales to process.')
    process.exit(1)
  }

  console.log(
    dryRun ? 'DRY RUN (no network)' : 'Translating',
    targets.map((t) => t.code).join(', '),
    '| namespaces:',
    nsToRun.join(', ')
  )

  for (const entry of targets) {
    const to = googleToForLocale(entry.code, entry.htmlLang)
    await translateLocale(entry.code, to, dryRun, nsToRun)
  }

  console.log('\nDone. Run: npm run i18n:check-keys && npx vue-tsc --noEmit')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
