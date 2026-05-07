/**
 * Read-only: for Settings → Interface language (`INTERFACE_LANGUAGE_PICKER_CODES`),
 * count message keys that still match `en` (common sign of leftover English copy).
 *
 * Default: merged bundles via `messages/<code>.ts`.
 * With `--bundles=canvas,mindmate,...`: compare only those namespace files (`messages/<code>/<ns>.ts`).
 *
 * Usage (from frontend/):
 *   npx tsx scripts/scan-picker-vs-en-parity.ts
 *   npx tsx scripts/scan-picker-vs-en-parity.ts --sample=30
 *   npx tsx scripts/scan-picker-vs-en-parity.ts --bundles=mindmate,canvas,sidebar,common --sample=0
 */
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { fileURLToPath } from 'node:url'

import { INTERFACE_LANGUAGE_PICKER_CODES } from '../src/i18n/locales'

const __dirnameRoot = dirname(fileURLToPath(import.meta.url))
const MESSAGE_ROOT_TS = join(__dirnameRoot, '../src/locales/messages')

type BundleFile =
  | 'admin'
  | 'auth'
  | 'canvas'
  | 'common'
  | 'community'
  | 'knowledge'
  | 'mindmate'
  | 'notification'
  | 'sidebar'
  | 'workshop'

function parseBundlesArg(): BundleFile[] | null {
  const arg = process.argv.find((a) => a.startsWith('--bundles='))
  if (!arg) return null
  const raw = arg.slice('--bundles='.length)
  const list = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean) as BundleFile[]
  const allowed = new Set<BundleFile>([
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
  ])
  for (const x of list) {
    if (!allowed.has(x)) {
      console.error(`Unknown bundle in --bundles: ${x}`)
      process.exit(1)
    }
  }
  return list.length > 0 ? list : null
}

function parseSampleArg(): number {
  const arg = process.argv.find((a) => a.startsWith('--sample='))
  if (!arg) return 12
  const n = Number.parseInt(arg.slice('--sample='.length), 10)
  return Number.isFinite(n) && n >= 0 ? Math.min(n, 200) : 12
}

function bucketForKey(keyLabel: string, usesBundles: boolean): string {
  if (usesBundles) {
    const idx = keyLabel.indexOf(':')
    return idx === -1 ? '(top)' : keyLabel.slice(0, idx)
  }
  const i = keyLabel.indexOf('.')
  return i === -1 ? '(top)' : keyLabel.slice(0, i)
}

async function loadBundle(code: string, bundle: BundleFile): Promise<Record<string, string>> {
  const filePath = join(MESSAGE_ROOT_TS, code, `${bundle}.ts`)
  const href = pathToFileURL(filePath).href
  const mod = (await import(href)) as { default: Record<string, string> }
  return mod.default
}

async function loadMerged(code: string): Promise<Record<string, string>> {
  const href = pathToFileURL(join(MESSAGE_ROOT_TS, `${code}.ts`)).href
  const mod = (await import(href)) as { default: Record<string, string> }
  return mod.default
}

async function mergedParity(
  enMerged: Record<string, string>,
  code: string
): Promise<{ equal: number; total: number; equalKeys: string[] }> {
  const loc = await loadMerged(code)
  let equal = 0
  const equalKeys: string[] = []
  const enKeys = Object.keys(enMerged)
  for (const k of enKeys) {
    if (!(k in loc)) {
      continue
    }
    if (loc[k] === enMerged[k]) {
      equal++
      equalKeys.push(k)
    }
  }
  const total = enKeys.filter((k) => k in loc).length
  return { equal, total, equalKeys }
}

function bundleOnlyParity(
  bundles: BundleFile[],
  enByBundle: Record<BundleFile, Record<string, string>>,
  locByBundle: Record<BundleFile, Record<string, string>>,
  equalKeysOut: string[]
): { equal: number; total: number } {
  let equal = 0
  let total = 0
  for (const b of bundles) {
    const enFlat = enByBundle[b]
    const locFlat = locByBundle[b]
    for (const k of Object.keys(enFlat)) {
      if (!(k in locFlat)) {
        continue
      }
      total++
      if (locFlat[k] === enFlat[k]) {
        equal++
        equalKeysOut.push(`${b}:${k}`)
      }
    }
  }
  return { equal, total }
}

function labelForMergedKey(enMerged: Record<string, string>, key: string): string {
  return enMerged[key] ?? ''
}

function labelForBundledKey(
  keyLabel: string,
  enByBundle: Record<BundleFile, Record<string, string>>
): string {
  const idx = keyLabel.indexOf(':')
  const ns = (idx === -1 ? 'mindmate' : keyLabel.slice(0, idx)) as BundleFile
  const bare = idx === -1 ? keyLabel : keyLabel.slice(idx + 1)
  const enFlat = enByBundle[ns]
  return enFlat?.[bare] ?? ''
}

async function main(): Promise<void> {
  const sample = parseSampleArg()
  const bundles = parseBundlesArg()
  const picker = INTERFACE_LANGUAGE_PICKER_CODES.filter((c) => c !== 'en')
  console.log('')
  console.log(
    bundles !== null
      ? `Picker vs en bundles: ${bundles.join(', ')}.`
      : 'Picker vs merged `en.ts` bundle.'
  )
  console.log(`Locales: ${picker.length}. Sample per locale: ${sample}.`)
  console.log('')

  const rows: { code: string; equal: number; total: number; pct: number }[] = []
  let enMerged: Record<string, string> | null = null
  const enBundled: Partial<Record<BundleFile, Record<string, string>>> = {}
  if (bundles === null) {
    enMerged = await loadMerged('en')
  } else {
    for (const b of bundles) {
      enBundled[b] = await loadBundle('en', b)
    }
  }

  const enByBundleResolved =
    bundles === null ? null : (enBundled as Record<BundleFile, Record<string, string>>)

  for (const code of picker) {
    let equal = 0
    let total = 0
    const equalKeys: string[] = []
    if (bundles === null) {
      if (!enMerged) {
        console.error('Internal error: missing merged EN bundle.')
        process.exit(1)
      }
      const m = await mergedParity(enMerged, code)
      equal = m.equal
      total = m.total
      equalKeys.push(...m.equalKeys)
    } else {
      if (!enByBundleResolved) {
        console.error('Internal error: missing EN bundle map.')
        process.exit(1)
      }
      const locByBundle: Partial<Record<BundleFile, Record<string, string>>> = {}
      for (const b of bundles) {
        locByBundle[b] = await loadBundle(code, b)
      }
      const hit = bundleOnlyParity(
        bundles,
        enByBundleResolved,
        locByBundle as Record<BundleFile, Record<string, string>>,
        equalKeys
      )
      equal = hit.equal
      total = hit.total
    }
    const pct = total === 0 ? 0 : Math.round((1000 * equal) / total) / 10
    rows.push({ code, equal, total, pct })

    const usesBundles = bundles !== null
    const byPrefix: Record<string, number> = {}
    for (const k of equalKeys) {
      const p = bucketForKey(k, usesBundles)
      byPrefix[p] = (byPrefix[p] ?? 0) + 1
    }
    const topPrefixes = Object.entries(byPrefix)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([p, n]) => `${p}:${n}`)
      .join(', ')

    console.log(`${code}\t${equal}/${total}\t(${pct}%)\t[${topPrefixes}]`)
    if (sample > 0 && equalKeys.length > 0) {
      for (const k of [...equalKeys].sort().slice(0, sample)) {
        let v = ''
        if (bundles === null) {
          if (!enMerged) {
            console.error('Internal error: missing merged EN bundle.')
            process.exit(1)
          }
          v = labelForMergedKey(enMerged, k)
        } else if (!enByBundleResolved) {
          console.error('Internal error: missing EN bundle map.')
          process.exit(1)
        } else {
          v = labelForBundledKey(k, enByBundleResolved)
        }
        const shown = v.length > 90 ? `${v.slice(0, 90)}…` : v
        console.log(`    ${k} = ${JSON.stringify(shown)}`)
      }
      if (equalKeys.length > sample) {
        console.log(`    … +${equalKeys.length - sample} more`)
      }
    }
    console.log('')
  }

  rows.sort((a, b) => b.equal - a.equal)
  console.log('Summary (most EN-equal keys first):')
  for (const r of rows) {
    console.log(`  ${r.code}\t${r.equal}/${r.total}\t(${r.pct}%)`)
  }
  console.log('')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
