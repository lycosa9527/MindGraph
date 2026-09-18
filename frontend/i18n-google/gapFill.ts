/**
 * Gap-fill UI locales from Simplified Chinese.
 * Keys still equal to English are translated zh-CN → target.
 */
import { existsSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { localeNamespaceBanner } from '../scripts/i18nFileBanner.ts'
import { translateBatch } from './googleBatch.ts'
import { isKeepFill } from './keepFill.ts'
import { type Namespace } from './namespaces.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
export const MESSAGES_ROOT = join(__dirname, '../src/locales/messages')

export interface GapRow {
  key: string
  zhText: string
}

export function collectGaps(
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

function escapeSq(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r\n/g, '\n').replace(/\n/g, '\\n')
}

function formatRecord(keysInOrder: string[], out: Record<string, string>): string {
  const lines = keysInOrder.map((k) => `  '${escapeSq(k)}': '${escapeSq(out[k])}',`)
  return `{\n${lines.join('\n')}\n}`
}

export function formatNamespaceExport(
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

export async function loadMod(locale: string, ns: Namespace): Promise<Record<string, string>> {
  const abs = join(MESSAGES_ROOT, locale, `${ns}.ts`)
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

export function writeNamespace(
  locale: string,
  ns: Namespace,
  keys: string[],
  out: Record<string, string>
): void {
  const body = formatNamespaceExport(ns, keys, out)
  const next = `${localeNamespaceBanner(locale, ns)}\n${body}`
  writeFileSync(join(MESSAGES_ROOT, locale, `${ns}.ts`), next, 'utf8')
}

export async function fillNamespace(
  locale: string,
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
  if (dryRun) {
    return { gap: gaps.length, kept: 0, failed: 0, sample }
  }
  if (gaps.length === 0) {
    writeNamespace(locale, ns, keys, out)
    return { gap: 0, kept: 0, failed: 0, sample }
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
